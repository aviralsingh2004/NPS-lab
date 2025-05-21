import socket
import json
import threading
import time
import queue

class NetworkDiscovery:
    def __init__(self, port=5000):
        self.port = port
        self.peers = {}
        self.peer_updates = queue.Queue()
        self.running = False
        self.broadcast_port = 5555
        self.local_ip = self._get_local_ip()
        
    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Use Google's DNS server to get local IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'

    def start(self):
        self.running = True
        
        # Start discovery thread
        self.discovery_thread = threading.Thread(target=self._discover_loop)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        
        # Start broadcast thread
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()
        
        print(f"Network discovery started on {self.local_ip}")

    def stop(self):
        self.running = False

    def _discover_loop(self):
        # Listen for broadcast messages
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', self.broadcast_port))
        
        print(f"Listening for peers on port {self.broadcast_port}")
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                peer_ip = addr[0]
                
                if peer_ip != self.local_ip:  # Don't add ourselves
                    try:
                        peer_data = json.loads(data.decode())
                        if peer_data.get('type') == 'discovery':
                            # Check if this is a new peer or an update
                            is_new = peer_ip not in self.peers
                            
                            self.peers[peer_ip] = {
                                'address': peer_ip,
                                'port': peer_data.get('port', self.port),
                                'last_seen': time.time(),
                                'status': 'active'
                            }
                            
                            if is_new:
                                print(f"New peer discovered: {peer_ip}")
                                self.peer_updates.put(('add', peer_ip))
                            
                            # Send acknowledgment
                            response = {
                                'type': 'discovery_ack',
                                'port': self.port
                            }
                            sock.sendto(json.dumps(response).encode(), (peer_ip, self.broadcast_port))
                            
                        elif peer_data.get('type') == 'discovery_ack':
                            if peer_ip in self.peers:
                                self.peers[peer_ip]['status'] = 'connected'
                                print(f"Peer {peer_ip} acknowledged")
                            
                    except json.JSONDecodeError:
                        print(f"Received invalid data from {peer_ip}")
                        
            except Exception as e:
                print(f"Error in discovery loop: {e}")
                
            # Clean up old peers
            current_time = time.time()
            for addr in list(self.peers.keys()):
                if current_time - self.peers[addr]['last_seen'] > 30:  # 30 seconds timeout
                    print(f"Peer {addr} timed out")
                    del self.peers[addr]
                    self.peer_updates.put(('remove', addr))
                    
    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while self.running:
            try:
                message = {
                    'type': 'discovery',
                    'port': self.port
                }
                sock.sendto(json.dumps(message).encode(), ('<broadcast>', self.broadcast_port))
                print(f"Broadcasting discovery message on port {self.broadcast_port}")
            except Exception as e:
                print(f"Error in broadcast loop: {e}")
                
            time.sleep(5)  # Broadcast every 5 seconds

    def get_peers(self):
        """Get list of active peers with their status"""
        return [{
            'address': addr,
            'status': self.peers[addr]['status']
        } for addr in self.peers.keys()]

    def get_updates(self):
        """Get any peer updates (additions/removals) since last check"""
        updates = []
        while not self.peer_updates.empty():
            updates.append(self.peer_updates.get())
        return updates 