# VM LIST AND CONDITION

## CONTROL PLANE (AWS) ✅ ACTIVE
IP: 16.79.90.160
PRIVATE IP: 172.31.4.113
HOST: ubuntu
RAM: 4 GB
CPU: 2 Core
STORAGE: 50 GB
Auth: pub key

## CONTROL PLANE (BCC Lab) ❌ ARCHIVED — NAT di port 11049, K3s port 6443 tidak bisa diakses dari Worker AWS
IP: proxy.bccdev.id
HOST: dev
PORT: 11049
RAM: 4 GB
CPU: 2 Core
STORAGE: 20 GB
Auth: pub key

## WORKER 1 (AWS)
IP: 15.232.116.101
PRIVATE IP: 172.31.2.62
HOST: ubuntu
RAM: 2 GB
CPU: 2 Core
STORAGE: 20 GB
Auth: pub key

## WORKER 2 (AWS)
IP: 15.232.71.54
HOST: ubuntu
RAM: 2 GB
CPU: 2 Core
STORAGE: 20 GB
Auth: pub key

# Domain
domain controlled by cloudflare titipin.me (frontend), can set api.titipin.me or titipin.me/api/v1 dll
DNS A records point to CP AWS: 16.79.90.160
