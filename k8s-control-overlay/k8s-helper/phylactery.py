################################################################################
# Author: Jonathan Decker
# Email: jonathan.decker@uni-goettingen.de
# Date: 2025-02-11
# Description: Service that helps set up and update control nodes in an HA setup
# Version: 1.0
################################################################################

import fcntl
import http.server
import socketserver
import os
import shutil
import struct
import subprocess
import socket
import urllib.request
import logging
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SHARED_FOLDER = "/share/phylactery"
PORT = 9999
SERVER_LINE_FORMAT = "    server {HOSTNAME} {IP}:6443 check verify none\n"
BASE_HAPROXY_CONFIG = f"{SHARED_FOLDER}/haproxy.cfg.base"
TARGET_HAPROXY_CONFIG = f"{SHARED_FOLDER}/haproxy.cfg"
INSTALL_HAPROXY_CONFIG = "/etc/haproxy/haproxy.cfg"
INTERFACE = "net0"

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        logger.info(f'Received GET request: {self.path}')
        import_config()
        restart_haproxy()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Request received')


def get_ip_address(ifname: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])

def record_node() -> None:
    # Get the hostname and IP address of the node
    hostname = socket.gethostname()
    ip_address = get_ip_address(INTERFACE)
    # Create a file in the shared directory to announce the node's presence
    announcement_file = f'{SHARED_FOLDER}/{hostname}_{ip_address}.txt'
    with open(announcement_file, 'w') as f:
        f.write(f'{hostname}_{ip_address}')

def send_request_to_nodes(nodes: list[tuple[str, str]]) -> None:
    # Send a GET request to each node
    for hostname, ip_address in nodes:
        try:
            url = f'http://{ip_address}:{PORT}/'
            logger.info(f'Sending GET request to {hostname} ({ip_address}:{PORT})')
            urllib.request.urlopen(url)
        except Exception as e:
            logger.error(f'Failed to send request to {hostname} ({ip_address}:{PORT}): {e}')

def discover_nodes() -> list[tuple[str, str]]:
    # Discover other nodes by reading files in the shared directory
    nodes = []
    for filename in os.listdir(SHARED_FOLDER):
        if filename.endswith('.txt'):
            filename_body = filename.replace('.txt', '')
            hostname, ip_address = filename_body.split('_')
            nodes.append((hostname, ip_address))
            logger.info(f'Discovered {hostname} from {ip_address}')
    return nodes

def construct_config(nodes: list[tuple[str, str]]) -> None:
    with open(BASE_HAPROXY_CONFIG, 'r') as f:
        haproxy_config = f.read()
    with open(TARGET_HAPROXY_CONFIG, 'w') as f:
        f.write(haproxy_config)
        for hostname, ip_address in nodes:
            f.write(SERVER_LINE_FORMAT.format(HOSTNAME=hostname, IP=ip_address))

def import_config() -> None:
    try:
        shutil.copyfile(TARGET_HAPROXY_CONFIG, INSTALL_HAPROXY_CONFIG)
    except Exception as e:
        logger.error(f'Failed to import config file: {e}')

def restart_haproxy() -> None:
    try:
        result = subprocess.run(['systemctl', 'restart', 'haproxy'], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        logger.info(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to restart haproxy: {e}')

def fix_etcd_membership(nodes: list[tuple[str, str]]) -> None:
    etcd_endpoints = ','.join(map(str, [node[1] + ":2379" for node in nodes]))
    logger.info(f'Using as etcd enpoints {etcd_endpoints}')
    if not os.path.exists("/share/pki/etcd/server.crt"):
        logger.info("No cluster up yet, skipping etcd check")
        return
    try:
        result_raw = subprocess.run(['etcdctl', '--endpoints', etcd_endpoints, '--cert=/share/pki/etcd/server.crt', '--key=/share/pki/etcd/server.key', '--cacert=/share/pki/etcd/ca.crt', '-w', 'json', 'member', 'list'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_json = json.loads(result_raw.stdout.decode())
        logger.info(result_json)
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to get etcd member list: {e}')
        return
    id_client_url_tuples = [(member['ID'], member['clientURLs'][0]) for member in result_json['members']]
    ip_address = get_ip_address(INTERFACE)
    ids = [id for id, url in id_client_url_tuples if ip_address in url]
    if len(ids)>0:
        try:
            logger.info(f"Removing member {ids[0]}")
            result_raw = subprocess.run(['etcdctl', '--endpoints', etcd_endpoints, '--cert=/share/pki/etcd/server.crt', '--key=/share/pki/etcd/server.key', '--cacert=/share/pki/etcd/ca.crt', '-w', 'json', 'member', 'remove', hex(ids[0])[2:]], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result_json = json.loads(result_raw.stdout.decode())
            logger.info(result_json)
        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to remove etcd member: {e}')

def fix_kubernetes_membership() -> None:
    path = '/share/kube.config'
    if not os.path.exists(path):
        logger.info("Kube config is not in share, cluster must not be ready")
        return
    hostname = socket.gethostname()
    try:
        result_raw = subprocess.run(['kubectl', 'get', 'nodes', '-o', 'json'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_json = json.loads(result_raw.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to get nodes via kubectl: {e}')
    node_names = [node['metadata']['name'] for node in result_json['items']]
    if hostname in node_names:
        try:
            logger.info("Removing self before rejoining")
            result_raw = subprocess.run(['kubectl', 'drain', hostname, '--delete-emptydir-data', '--force', '--ignore-daemonsets'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error('Failed to drain node: {e}')
        try:
            result_raw = subprocess.run(['kubectl', 'delete', 'node', hostname], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error('Failed to delete node: {e}')

def set_ready_mark() -> None:
    path = '/root/phylactery_ready'
    if not os.path.exists(path):
        open(path, 'w').close()

def main() -> None:
    # Record node in folder
    record_node()
    # Discover other nodes
    nodes = discover_nodes()
    # construct new config
    construct_config(nodes)
    # Import config
    import_config()
    # Restart HAProxy
    restart_haproxy()
    # Send a GET request to each node
    send_request_to_nodes(nodes)
    # Checks if IP is still an etcd member and removes member status so it can rejoin
    fix_etcd_membership(nodes)
    # Check if node with the same hostname is part of the kubernetes cluster and remove it so it can rejoin
    fix_kubernetes_membership()
    # Create a final to signal that phylactery is ready and install script can proceed
    set_ready_mark()
    # Start the HTTP server
    with socketserver.TCPServer(('', PORT), RequestHandler) as httpd:
        logger.info(f'Starting HTTP server on port {PORT}')
        httpd.serve_forever()

if __name__ == '__main__':
    main()
