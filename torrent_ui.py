import time, threading, operator
import mc
from transmission_client import TransmissionClient, TransmissionClientFailure
from rtorrent_client import RTorrentXMLRPCClient


config = mc.GetApp().GetLocalConfig()
window = mc.GetWindow(14002)
torrent_list = window.GetList(100)


class TorrentUI(threading.Thread):
    '''
    Base class for torrent client object. Extend this class with the required methods
    for torrent clients.
    
    Arguments:
        connection: A connection object, usually created when checking connectivity of
        a torrent client
    '''
    
    order = "alphabetical"
    stored_order = config.GetValue('order')
    if stored_order:
        order = stored_order
    
    
    def __init__(self, connection):
        super(TorrentUI, self).__init__()
        self.connection = connection
        self._stop = threading.Event()
        

    def run(self):
        self.window = window
        self.refresh_list = False
        
        # Start updating the torrent list.
        self.update_list(firstrun=True)
        
        
    def get_status(self):
        '''
        Extend this to get status information. Mainly for getting global up/down speeds.
        '''
        raise NotImplementedError("You must extend this method to get status information.")
        
    
    def get_torrents(self):
        '''
        Extend this to get torrent information for use in other methods.
        Should return a list of dicts with torrent information.
        A torrent list item should contain these variables:
            'label': <string>,
            'status': <string> options: 'Downloading', 'Seeding', 'Paused', 'Unknown'
            'total_size': <string> example: "20 MB"
            'size_downloaded': <string> example: "20 MB"
            'size_uploaded': <string> example: "20 MB"
            'percent_done': <string> example: "56%"
            'estimated_time': <string> example: "2 hrs, 32 mins, 10 sec"
            'peers_connected': <int>
            'peers_incoming': <int>
            'peers_outgoing': <int>
            'rate_download': <string> example: "150 KB" (per second)
            'rate_upload': <string> example: "150 KB" (per second)
            'ratio': <float>
            
            These values may be created using the built in `format_filesize` and
            `format_time` methods.
        '''
        raise NotImplementedError("You must extend this method to return a list of torrents.")
    
    
    def start_torrent(self, id=False):
        '''
        Extend this to start torrents. If the `id` argument is False, start all torrents, 
        else start the torrent with the specified `id`.
        '''
        raise NotImplementedError("You must extend this method to start torrents.")
        
    
    def stop_torrent(self, id=False):
        '''
        Extend this to stop torrents. If the `id` argument is False, stop all torrents, 
        else start the torrent with the specified `id`.
        '''
        raise NotImplementedError("You must extend this method to stop torrents.")
        
        
    def delete_torrent(self, id, files=False):
        '''
        Extend this to delete torrents. The `files` option should be true to delete files
        associated with this torrent download.
        '''
        raise NotImplementedError("You must extend this method to stop torrents.")
        
      
    def format_filesize(self, bytes, labels=True):
        '''
        Formats an integer representation of bytes to a human-readable 
        unit representation.
        Can optionally turn off unit labels to get integers back.
        '''
        bytes = float(bytes)
        if bytes >= 1099511627776:
            terabytes = bytes / 1099511627776
            size = '%.1f' % terabytes; unit = 'TB'
        elif bytes >= 1073741824:
            gigabytes = bytes / 1073741824
            size = '%.1f' % gigabytes; unit = 'GB'
        elif bytes >= 1048576:
            megabytes = bytes / 1048576
            size = '%.1f' % megabytes; unit = 'MB'
        elif bytes >= 1024:
            kilobytes = bytes / 1024
            size = '%.1f' % kilobytes; unit = 'KB'
        else:
            size = '%.1f' % bytes; unit = 'b' 
           
        size = size.strip('.0') 
        if str(size).strip() == '':
            size = 0
        if labels:
            return '%s %s' % (size, unit)
        else:
            return size
            
            
    def format_time(self, seconds, add_s=False):
        '''
        Formats an integer representation of seconds to a human-readable 
        unit representation. For time estimation.
        '''
        time = []
        parts = [('yrs', 60 * 60 * 24 * 7 * 52),
                 ('wks', 60 * 60 * 24 * 7),
                 ('days', 60 * 60 * 24),
                 ('hr', 60 * 60),
                 ('min', 60)]
        for suffix, length in parts:
            value = seconds / length
            if value > 0:
                seconds = seconds % length
                time.append('%s%s' % (str(value),(suffix, (suffix, suffix + 's')[value > 1])[add_s]))
            if seconds < 1:
                break
        return ' '.join(time)

        
    def create_item_from_torrent(self, torrent):
        '''
        Creates a ListItem from a torrent dict. Used when adding torrents to
        the list.
        '''
        item = mc.ListItem(mc.ListItem.MEDIA_FILE)
        item.SetLabel(torrent['label'])
        item = self.update_item_from_torrent(item, torrent)
        self.refresh_list = True
        return item
    
    
    def update_item_from_torrent(self, item, torrent):
        '''
        Updates torrent information display.
        Does not refresh the list, just makes changes on the fly.
        '''
        description1 = ''
        description2 = ''
        # Create display info in a format relevant to the torrent status.
        if torrent['status'] == 'Downloading':
            description1 = "%s of %s (%s) - %s" % (
                torrent['size_downloaded'],
                torrent['size_total'],
                '%s%%' % torrent['percent_done'],
                torrent['estimated_time']
            )
            description2 = "Downloading from %s of %s peers - DL:%s/s UL:%s/s" % (
                torrent['peers_incoming'],
                torrent['peers_connected'],
                torrent['rate_download'],
                torrent['rate_upload']
            )
        elif torrent['status'] == 'Seeding':
            description1 = "%s, uploaded %s (Ratio %s)" % (
                torrent['size_total'],
                torrent['size_uploaded'],
                torrent['ratio']
            )
            description2 = "Seeding to %s of %s peers - UL:%s/s" % (
                torrent['peers_outgoing'],
                torrent['peers_connected'],
                torrent['rate_upload']
            )
        elif torrent['status'] == 'Paused':
            if torrent['percent_done'] == '100%':
                description1 = "%s, uploaded %s (Ratio %s)" % (
                    torrent['size_total'],
                    torrent['size_uploaded'],
                    torrent['ratio']
                )
            else:
                description1 = "%s of %s (%s)" % (
                    torrent['size_downloaded'],
                    torrent['size_total'],
                    '%s%%' % torrent['percent_done']
                )
            description2 = "Paused"
        # Attach things to the ListItem for later use.
        item.SetProperty("transfer_status", torrent['status'])
        item.SetProperty("id", torrent['id'])
        item.SetDescription(description1)
        item.SetProperty("progress_bar", str(int(round(torrent['percent_done'], -1))) )
        item.SetTagLine(description2)
        
        return item


    def update_list(self, firstrun=False):
        '''
        Main function for updating the torrent list. Usually run in a loop.
        Gets torrents, makes ListItems out of them and populates the list.
        '''
        # Set true when the list needs to be refresh because of added torrents
        self.refresh_list = False
        
        torrents = self.get_torrents()
        
        # On the first run, create all torrent items.
        if firstrun:
            items = mc.ListItems()
            for torrent in torrents:
                item = self.create_item_from_torrent(torrent)
                items.append(item)
                # Update the global status items.
            status = self.get_status()
            window.GetControl(2000).SetVisible(True)
            window.GetLabel(2001).SetLabel(str(status['global_download']))
            window.GetControl(2002).SetVisible(True)
            window.GetLabel(2003).SetLabel(str(status['global_upload']))  
            self.window.GetControl(105).SetVisible(False)
            
        else:
            # Wait for 2 seconds, this will later be switched to a var that
            # can be changed by the user.
            time.sleep(2.0)
            
            self.window.GetControl(105).SetVisible(False)
            
            # List of current items.
            try:
                current_items = torrent_list.GetItems()
            except:
                return
            
            current_ids = {}
            count = 0
            for item in current_items:
                current_ids[item.GetProperty('id')] = count
                count += 1
            
            torrent_ids = []
            
            new_items = mc.ListItems()
            
            for torrent in torrents:
                # Existing torrent, update the current ListItem.
                if torrent['id'] in current_ids.keys():
                    item = current_items[current_ids[torrent['id']]]
                    self.update_item_from_torrent(item, torrent)

                # This torrent is not in the current list, create a ListItem.
                else:
                    item = self.create_item_from_torrent(torrent)
                    new_items.append(item)
                

                torrent_ids.append(torrent['id'])
                
            try:
                # Update the global status items.
                status = self.get_status()
                window.GetControl(2000).SetVisible(True)
                window.GetLabel(2001).SetLabel(str(status['global_download']))
                window.GetControl(2002).SetVisible(True)
                window.GetLabel(2003).SetLabel(str(status['global_upload']))  
            except:
                print "Killing the TorrentUI thread."
                self._stop.set()
                
            new_ids = []
            for current_id in current_ids.keys():
                if current_id in torrent_ids:
                    new_ids.append(current_id)
                    
            for new_id in new_ids:
                new_items.append(torrent_list.GetItem(current_ids[new_id]))
    
            items = current_items
            if len(new_items) != len(current_items):
                self.refresh_list = True
                items = new_items
        
        # If the list needs to be refreshed, do it. When you call SetItems()
        # on a list, it loses it's focus and you end up at the top again.
        if self.refresh_list:
            # Try to get the currently selected item.
            try:
                selected = torrent_list.GetFocusedItem()
            except:
                pass
            # Set the new list values.
            torrent_list.SetItems(items)
            # Try to restore the previously selected item.
            try:
                torrent_list.SetFocusedItem(selected)
            except:
                pass
                
        # Do it all again.
        self.update_list()
    
    
    def sort_torrents(self, sort_type):
        items_dict = {}
        
        if sort_type == "alphabetical":
            for item in torrent_list.GetItems():
                items_dict[item.GetLabel()] = item
            labels = items_dict.keys()
            labels.sort()
            ordered_list = []
            for label in labels:
                ordered_list.append(items_dict[label])
        elif sort_type == "status":
            down = []; seed = []; pause = []
            for item in torrent_list.GetItems():
                if item.GetProperty('transfer_status') == 'Downloading':
                    down.append(item)
                if item.GetProperty('transfer_status') == 'Seeding':
                    seed.append(item)
                if item.GetProperty('transfer_status') == 'Paused':
                    pause.append(item)
            ordered_list = down + seed + pause
        
        window.GetLabel(104).SetLabel(sort_type.upper())
        print ordered_list
        
        list_items = mc.ListItems()        
        for item in ordered_list:
            list_items.append(item)
            
        torrent_list.SetItems(list_items)
        

class TransmissionUI(TorrentUI):
         
    
    def get_status(self):
        status = self.connection.sessionStats()['arguments']
        status = {
            'global_download': '%s/s' % self.format_filesize(status['downloadSpeed']), 
            'global_upload': '%s/s' % self.format_filesize(status['uploadSpeed'])
        }
        return status
        
         
    def get_torrents(self):
        feed_torrents = self.connection.torrentGet()['arguments']['torrents']
        torrents = []
        
        for torrent_data in feed_torrents:
        
            total_bytes_completed = 0
            for payload in torrent_data['files']:
                total_bytes_completed += payload['bytesCompleted']
        
            if torrent_data['status'] == 4:
                status = 'Downloading'
            elif torrent_data['status'] == 8:
                status = 'Seeding'
            elif torrent_data['status'] == 16:
                status = 'Paused'
            else:
                status = 'Unknown'
            
            if torrent_data['percentDone']*100 == 100.0:
                torrent_data['percentDone'] = 1
        
            torrents.append({
                'id': str(torrent_data['id']),
                'label': str(torrent_data['name']),
                'status': status,
                'size_total': self.format_filesize(torrent_data['totalSize']),
                'size_downloaded': self.format_filesize(total_bytes_completed),
                'size_uploaded': self.format_filesize(torrent_data['uploadedEver']),
                'percent_done': (torrent_data['percentDone']*100),
                'estimated_time': self.format_time(torrent_data['eta']),
                'peers_connected': torrent_data['peersConnected'],
                'peers_incoming': torrent_data['peersSendingToUs'],
                'peers_outgoing': torrent_data['peersGettingFromUs'],
                'rate_download': self.format_filesize(torrent_data['rateDownload']),
                'rate_upload': self.format_filesize(torrent_data['rateUpload']),
                'ratio': str(torrent_data['uploadRatio'])
            })
            
        return torrents
        
        
    def start_torrent(self, id=False):
        print "Starting torrent"
        if id:
            print "Starting torrent with id: %s" % id
            self.connection.torrentStart(torrents=id)
        else:
            print "Starting all torrents"
            self.connection.torrentStart()
        
        
    def stop_torrent(self, id=False):
        if id:
            self.connection.torrentStop(torrents=id)
        else:
            self.connection.torrentStop()
        
        
    def delete_torrent(self, id, files=False):
        if id:
            self.connection.torrentRemove(torrents=id, files=files)
        else:
            self.connection.torrentRemove(files)
        
        
class rTorrentUI(TorrentUI):


    def get_status(self):
        print "get_status Ran"
        print "Methods: %s" % status
        status = {
            'global_download': '%s/s' % self.format_filesize(status['downloadSpeed']), 
            'global_upload': '%s/s' % self.format_filesize(status['uploadSpeed'])
        }
        return status

         
    def get_torrents(self):
        
        conn = self.connection
        
        torrents = []
        
        views = ['started', 'stopped', 'seeding']
        for view in views:
            infohashes = conn.download_list(view)
            for infohash in infohashes:
                print "up_total: %s" % conn.d.get_up_total(infohash)
                
             
                if view == 'started':
                    status = 'Downloading'
                elif view == 'seeding':
                    status = 'Seeding'
                elif view == 'stopped':
                    status = 'Paused'
                else:
                    status = 'Unknown'
                print status
                
                total = int(conn.d.get_size_bytes(infohash))
                completed = int(total)-int(conn.d.get_left_bytes(infohash))
                print "total: %s" % total
                print "completed: %s" % completed
                percent = (float(completed)*100.00)/float(total)
                print "percent: %s" % percent
                torrents.append({
                    'id': str(infohash),
                    'label': str(conn.d.get_name(infohash)),
                    'status': status,
                    'size_total': self.format_filesize(total),
                    'size_downloaded': self.format_filesize(completed),
                    'size_uploaded': self.format_filesize(conn.d.get_up_total(infohash)),
                    'percent_done': percent,
                    'estimated_time': self.format_time(torrent_data['eta']),
                    'peers_connected': conn.d.get_peers_connected(infohash),
                    'peers_incoming': conn.d.get_ratio(infohash),
                    'peers_outgoing': conn.d.get_ratio(infohash),
                    'rate_download': self.format_filesize(conn.d.get_down_rate(infohash)),
                    'rate_upload': self.format_filesize(conn.d.get_up_rate(infohash)),
                    'ratio': conn.d.get_ratio(infohash)
                })
            
        return torrents

    
def create_connection(url=False, stored_url=False):
    connection = False
    connected = False
    klass = False
    
    if stored_url:
        url = stored_url
    
    print "Connecting with url: %s" % url
    
    TORRENT_CLIENTS = [{
        'name': 'Transmission',
        'ui_klass': TransmissionUI,
        'connection_klass': 'TransmissionClient(rpcUrl=\'{{url}}\')'
        'default_url': 'http://localhost:9091'
    },
#     {
#         'name': 'rTorrent',
#         'ui_klass': rTorrentUI,
#         'connection_klass': 'RTorrentXMLRPCClient(\'scgi://%s\' % \'{{url}}\'.strip(\'http://\'))'
#         'default_url': 'scgi://127.0.0.1:5000'
#     }
    ]
    
    for client in TORRENT_CLIENTS:
        mc.ShowDialogNotification("Trying to connect to %s" % client['name'])
        # build connection command
        try:
            if url:
                connection = eval(client['connection_klass'].replace('{{url}}', url))
            else:
                connection = eval(client['connection_klass'].replace('{{url}}', client['default_url']))
            connected = client
        except:
            connected = False
            print "%s connection failed: %s" % (client['name'], e)
            pass
        if connected:
            break

    # Made a connection, continue...
    if connected:
        window.GetLabel(105).SetLabel("Loading torrents...")
        connection = connected['ui_klass'](connection)
        connection.start()
        print "Made a connection, starting UI"
        return connection
    # Found and tried a stored url but it didn't work, try again without the url.
    elif stored_url: 
        print "Manual IP didn't work, trying factory ones."
        config.SetValue('client_address', 'none')
        return create_connection()
    # Not a stored url and the factory ones didn't work, ask for a manual IP...
    else:
        if mc.ShowDialogConfirm("Is there a torrent app running?", "Would you like to supply a manual IP and port for the torrent client?", "Quit", "Manual IP"):
            if config.GetValue('client_address'):
                value = config.GetValue('client_address')
            else:
                value = 'e.g.: "http://localhost:9091"'
            value = mc.ShowDialogKeyboard("Manual IP Entry", value, False)
            if value != 'e.g.: "http://localhost:9091"':
                config.SetValue('client_address', value)
            create_connection(stored_url=value)
        else:
            mc.CloseWindow()
        
            
url = config.GetValue('client_address')
if url and url != 'none': 
    print "Saved IP Retrieved: %s" % url
    connection = create_connection(stored_url=url)
else:
    connection = create_connection()
    