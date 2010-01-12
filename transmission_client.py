#!/usr/bin/env python
try:
    import simplejson as json
except ImportError:
    import json
import urllib2
import sys


class TransmissionClientFailure(Exception): pass

class TransmissionClient(object):
  
    rpcUrl = None
    headers = {}


    def __init__( self, rpcUrl='http://localhost:9091'):
        """ try to do a stupid call to transmission via rpc """

        try:
            self.rpcUrl = rpcUrl
            if not self.rpcUrl.endswith("/transmission/rpc"):
                self.rpcUrl = '%s/transmission/rpc' % rpcUrl 
            req = urllib2.Request( self.rpcUrl , {}, self.headers)
            response = urllib2.urlopen(req)
            response = response.read()
            if not response.find("no method name"):
                raise TransmissionClientFailure, "Make sure your transmission-daemon is running %s" % e             
                
        except urllib2.HTTPError, e:
            if e.code == 409:
                self.headers['X-Transmission-Session-Id'] = e.info()['X-Transmission-Session-Id']
                return self.__init__( self.rpcUrl )
            else:
                raise Exception('HTTPError: %s' % e.code )
        except Exception, e:
            raise TransmissionClientFailure, "Make sure your transmission-daemon is running %s" % e


    def _rpc( self, method, params={} ):
        """ generic rpc call to transmission """
        
        try:
            params['ids'] = int(params['ids'])
        except:
            pass

        data = { 'method': method, 'arguments': params}
        postdata = json.dumps(data)
        try:
            req = urllib2.Request( self.rpcUrl , postdata, self.headers)
            response = urllib2.urlopen(req)
            return json.loads(response.read())
        except urllib2.HTTPError, e:
            if e.code == 409:
                self.headers['X-Transmission-Session-Id'] = e.info()['X-Transmission-Session-Id']
                return self._rpc(method, params)
            else:
                raise Exception('HTTPError: %s' % e.code )
            
            
    def sessionStats( self ):
        return self._rpc( 'session-stats' )
    

    def torrentGet( self, torrentIds=[], fields=[ 'id', 'name', 'totalSize', 'percentDone', 'rateDownload', 'rateUpload', 'files', 'status', 'peersConnected', 'peersSendingToUs', 'peersGettingFromUs', 'eta', 'uploadedEver', 'uploadRatio']):
        if len(torrentIds) > 0:
            return self._rpc( 'torrent-get', { 'ids': torrentIds, 'fields': fields } ) 
        return self._rpc( 'torrent-get', { 'fields': fields } )


    def torrentAdd( self, torrentFile, downloadDir='.' ):
        return self._rpc( 'torrent-add', { 'filename': torrentFile, 'download-dir': downloadDir } )


    def torrentRemove( self, torrents=None, files=False ):
        if files:
            if torrents:
                return self._rpc( 'torrent-remove', { 'ids': torrents, 'delete-local-data': 'true' } )
            else:
                return self._rpc( 'torrent-remove', { 'delete-local-data': 'true' } )
        if torrents:
            return self._rpc( 'torrent-remove', { 'ids': torrents } )
        else:
            return self._rpc( 'torrent-remove', { } ) 
    
    
    def torrentStart( self, torrents=None ):
        if torrents:
            return self._rpc( 'torrent-start', { 'ids': torrents } )
        else:
            return self._rpc( 'torrent-start', {} )
        
        
    def torrentStop( self, torrents=None ):
        if torrents:
            return self._rpc( 'torrent-stop', { 'ids': torrents } )
        else:
            return self._rpc( 'torrent-stop', {} )