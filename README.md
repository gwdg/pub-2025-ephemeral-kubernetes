# Ephemeral Kubernetes

This repository provides a proof of concept for an Ephemeral Kubernetes deployment.
It uses Warewulf to provision a set of nodes including at least 3 control nodes.
The provided scripts perform an offline installation of Kubernetes and configure a HA setup with Keepalived and HAProxy.

Moreover, the code includes a service called Phylactery, which ensures that nodes that are rebooted properly rejoin the cluster.

Setting up a cluster from scratch takes less than 90 seconds.

As the nodes are handled via Warewulf, they do not include persistant storage by default.
Persisting data beyond reboots requires additional configuration.

## Installation

### OpenStack
The code was tested in an OpenStack environment but should work with any Warewulf setup (tested with v4.5.8 on Rocky 9.4).
If Warewulf is already installed, move on to Ephemeral Kubernetes Configuration.

To boot images via Warewulf in OpenStack, an image or volume is required that starts into a PXE boot sequence.

Create a new network for the cluster (this might require additional quota)
- Name the network "private-pxe"
- Set Admin State to True
- Set Create Subnet to True
- Name the Subnet "private-pxe-subnet"
- Set the Network Address to "10.0.0.0/24"
- Set Disable Gateway to True
- In Subnet Details set Enable DHCP to False and Allocation Pools to "10.0.0.1,10.0.0.254"

Create a new VM as the manager node
- Name it "cluster-manager"
- Use Rocky 9.4
- Use a flavor with sufficient resources
- Add your ssh key

Create security group
- Create "cluster-manager" security group
- Add a rule for SSH with a CIDR that is reachable from your workstation
- Assign the group to the cluter-manager VM
- Associate a floating IP with the cluster-manager VM
- Ensure that you can login via SSH into the VM

Create the cluster node VMs
- Create at least 3 VMs as control nodes named control0, control1, etc.
- Create zero or more worker nodes named worker0, worker1, etc.
- Set the pxe-boot image or volume for them
- After creating all nodes got To Networks, private-pxe and Ports and disable Port Security for all control and worker nodes

### Warewulf
On the cluster-manager node proceed with the following steps:

- `dnf update -y`
- `dnf install https://github.com/warewulf/warewulf/releases/download/v4.5.8/warewulf-4.5.8-1.el9.x86_64.rpm`
- edit `/etc/warewulf/warewulf.conf` and set ipaddr to the internal IP of the cluster-manager VM, for example, 10.0.0.13, set network mask to 255.255.255.0 and set DHCP range to 10.0.0.1 to 10.0.0.254
- `wwctl configure --all`
- `sudo systemctl enable --now warewulfd`
- Check with `sudo wwctl server status`
- `wwctl container import docker://ghcr.io/hpcng/warewulf-rockylinux:9`
- `wwctl container exec warewulf-rockylinux:9 /bin/sh`
    - `dnf install -y nano`
    - `exit`

Add the nodes in Warewulf
- `wwctl node add control 0`
- `wwctl node set --container warewulf-rockylinux:9 control0`
- `wwctl node set --hwaddr <MAC ADDR> control0` The MAC Address can be found under Instances, control0, Interfaces
- `wwctl node set --ipaddr <IP ADDR> control0` The IP Address can be found in the same interface as the MAC Address
- `wwctl node set --netmask 255.255.255.0 control0`
- `wwctl node set --netdev net0 control0`

Do so for all control and worker nodes.
- `wwctl configure -a`

In OpenStack reboot the VMs and check console to ensure the nodes properly boot.
- Test out that the nodes are running `ssh control0` or `ssh <IP ADDR>`

### Ephemeral Kubernetes Configuration.
Setup an NFS share, which will be used to share tokens and certs between the nodes.
- Edit `/etc/warewulf/warewulf.conf` and under nfs add
```
  - path: /share  
   export options: rw,sync,no_root_squash  
   mount options: defaults  
   mount: true
```
- `wwctl configure -a`
- `wwctl overlay build control0`

Create the overlay to be used by the cluster
- `wwctl overlay create k8s-control`

Clone this repository and cd into it.
- Set the IP of the cluster manager as `--apiserver-cert-extra-sans=<IP ADDR` in `k8s-control-overlay/k8s-helper/k8s-install.sh`, the default is 10.0.0.13
- `cp -r k8s-control-overlay /var/lib/warewulf/overlays/k8s-control`
- `cd k8s-images`
    - `./download-images.sh` This repo uses Kubernetes 1.32.1 by default
    - `./copy-images.sh`
    - `cd -`
- Edit `/var/lib/warewulf/overlays/hosts/rootfs/etc/hosts.ww` and add `10.0.0.99 vip.kubernetes.local` This sets the DNS entry for the virtual IP used by keepalived for the HA setup on the control nodes
- `cd ww-image-builder`
    - `./build-and-import.sh` this may take some time
    
There are two container images, k8s-base-ww and k8s-control-ww.
The worker nodes should use k8s-base-ww and the control nodes k8s-control-ww.
- `wwctl node set --container k8s-control-ww control[0-99]`
- `wwctl node set --container k8s-base-ww worker[0-99]`

Worker and control should both use the k8s-control overlay.
- `wwctl node set -O wwinit,k8s-control control[0-99]`
- `wwctl node set -O wwinit,k8s-control worker[0-99]`

Set rootfs to tmpfs so containerd works as otherwise pivot root will fail
- `wwctl node set --root tmpfs control[0-99]`
- `wwctl node set --root tmpfs worker[0-99]`

Reconfigure and build
- `wwctl configure -a`
- `wwctl overlay build`

Deploy everything
- `wwctl ssh control[0-99] reboot`
- `wwctl ssh worker[0-99] reboot`

After about 90 seconds the cluster is ready.
This can be seen as in /share multiple files should appear including `leader` for the node that initialized the cluster `leader_ready` as the signal that the cluster is operational and the other nodes can join and `kube.config` as the admin kube config file.

The warewulf subnet was tested on the subnet 10.0.0.0/24 with 10.0.0.13 as the host for Warewulf and 10.0.0.99 as the virtual IP for the HA setup.
The HA setup uses vip.kubernetes.local on port 8443.

#### Kubectl from cluster manager
Install kubectl on the cluster manager ( https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/ ).
Set `export KUBECONFIG=/share/kube.config` in `.bashrc`.

Now you can run `kubectl get nodes`, `kubectl get pods -A` from the cluster manager.

## Usage

After completing installation steps, the cluster can be rebooted using the `rebuild-and-restart.sh` script, which clears the files from the /share folder before restarting all nodes.
This effectively resets the cluster and causes it to be recreated.

The cluster persists if only a single control node is restarted at a time.
Worker nodes can be restarted arbitrarily.

Via `wwctl overlay edit k8s-control /k8s-helper/k8s-install.sh` additional yaml files can be loaded by the leader after the cluster is initalized.
These yaml files should also be added to the overlay if the nodes do not have internet access.

## How it works

When the nodes start
- The k8s-install systemd service is triggered on each of them
- This runs /k8s-helper/k8s-install.sh
- The first node to run this script up to a certain point claims leadership to initialize the cluster
- To signal this to the other nodes, the leader creates a file `/share/leader`
- The other nodes now all wait for the file `/share/leader_ready` to appear
- The leader intializes the cluster and copies the certificates to `/share/pki` and the kubeconfig to `/share/kube.config`
- While initializing the control nodes also start a service called `phylactery`, which on start-up adds the node to a shared configuration for the HAProxy setup
- The `phylactery` service then checks if a node with the same name or IP already exists in the cluster, which is left over from the node being rebooted, and removes it so the node can properly rejoin
- Then the `phylactery` service exposes an HTTP server that can be called to trigger a refresh of the HAProxy configuration
- Once the leader has finished initializing the cluster, it adds kube-flannel as the CNI and creates the file `/share/leader_ready`
- All other nodes can now proceed, using the kubeconfig under share to join the cluster

When a node is restarted
- When restarting a worker node, it checks if a node with the same name is already in the cluster and if yes, removes it and then joins
- When restarting a control node, it starts its `phylactery` service, which checks if there is already a node with the same name in the cluster or in the etcd members list and removes them before rejoining

Limitations
- etcd supports recovery from up to `(N-1)/2` nodes failing, which for a 3 node cluster is 1, so if 2 out of 3 nodes fail, the cluster cannot recover on its own (see https://etcd.io/docs/v3.5/op-guide/recovery/)
    - In this case, the cluster can be reset by rebooting all nodes, this is not detected automatically
