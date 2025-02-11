#!/bin/bash

# List of image tags
IMAGE_TAGS=(
  "registry.k8s.io/kube-apiserver:v1.32.1"
  "registry.k8s.io/kube-controller-manager:v1.32.1"
  "registry.k8s.io/kube-scheduler:v1.32.1"
  "registry.k8s.io/kube-proxy:v1.32.1"
  "registry.k8s.io/coredns/coredns:v1.11.3"
  "registry.k8s.io/pause:3.10"
  "registry.k8s.io/pause:3.9"
  "registry.k8s.io/pause:3.8"  
  "registry.k8s.io/etcd:3.5.16-0"
  "ghcr.io/flannel-io/flannel:v0.26.4"
  "ghcr.io/flannel-io/flannel-cni-plugin:v1.6.2-flannel1"
)

# Loop through each image tag
for IMAGE_TAG in "${IMAGE_TAGS[@]}"; do
  # Pull the image
  echo "Pulling image: $IMAGE_TAG"
  docker pull "$IMAGE_TAG"

  # Get the image name and tag
  IMAGE_NAME="${IMAGE_TAG%:*}"
  IMAGE_TAG_NAME="${IMAGE_TAG##*:}"

  # Export the image as a tar file
  echo "Exporting image: $IMAGE_TAG"
  docker save -o "${IMAGE_NAME##*/}_${IMAGE_TAG_NAME}.tar" "$IMAGE_TAG"

  # Verify the tar file
  echo "Verifying tar file: ${IMAGE_NAME##*/}_${IMAGE_TAG_NAME}.tar"
  tar -tf "${IMAGE_NAME##*/}_${IMAGE_TAG_NAME}.tar"
done
