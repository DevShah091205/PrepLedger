# Deploying PrepLedger on AWS (EC2 + Docker)

Time: about 30 minutes. Cost: a t3.micro (or t2.micro) instance fits the free tier. Check **Billing → Free Tier** in your account to see what your plan covers, and set a budget alert first.

```
Browser ──> Caddy (:80/:443, automatic HTTPS) ──> FastAPI in Docker ──> SQLite on the instance disk
                                                        └── daily backup ──> S3 bucket
```

## 1. Before you start
1. Sign in to the AWS Console. Turn on MFA for the root user.
2. **Billing → Budgets → Create budget**: a zero-spend or Rs.500 budget with an email alert.
3. Pick one region (top-right) and stay in it. Mumbai (ap-south-1) is closest for India.

## 2. Create the S3 bucket for backups
1. **S3 → Create bucket**. Name: `prepledger-yourname-backups`. Keep *Block all public access* ON.
2. Leave default encryption on. Create.

## 3. Create an IAM role for the server
1. **IAM → Policies → Create policy → JSON**, paste, replace the bucket name, save as `PrepLedgerBackup`:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:PutObject"],
       "Resource": "arn:aws:s3:::prepledger-yourname-backups/*"
     }]
   }
   ```
2. **IAM → Roles → Create role** → AWS service → **EC2** → attach `PrepLedgerBackup` → name `PrepLedgerEC2Role`.

## 4. Launch the EC2 instance
1. **EC2 → Launch instance**. Name `prepledger`.
2. Image: **Amazon Linux 2023**. Type: **t3.micro**.
3. **Key pair → Create new** (`prepledger-key`, RSA, `.pem`). Save the downloaded file.
4. **Network settings → Create security group**:
   - SSH (22): source **My IP**
   - HTTP (80): Anywhere
   - HTTPS (443): Anywhere
5. Storage: 12 GB gp3.
6. **Advanced details → IAM instance profile**: `PrepLedgerEC2Role`.
7. Launch. Then **EC2 → Elastic IPs → Allocate Elastic IP address → Associate** it to the instance, so the address never changes.

## 5. Install Docker on the server
On your computer (use the folder where the `.pem` file is):
```bash
chmod 400 prepledger-key.pem
ssh -i prepledger-key.pem ec2-user@<ELASTIC_IP>
```
On Windows 10/11 the same `ssh` command works in PowerShell. Then, on the server:
```bash
sudo dnf install -y docker unzip cronie
sudo systemctl enable --now docker crond
sudo usermod -aG docker ec2-user
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
exit
```
Log in again so the docker group applies, and check `docker compose version`.

## 6. Upload the project and configure it
From your computer, in the folder containing the zip:
```bash
scp -i prepledger-key.pem prepledger.zip ec2-user@<ELASTIC_IP>:~
ssh -i prepledger-key.pem ec2-user@<ELASTIC_IP>
unzip prepledger.zip && cd prepledger
cp .env.example .env
nano .env
```
In `.env` set a real secret (generate one with `openssl rand -hex 32`):
```
JWT_SECRET=<paste it here>
TZ_OFFSET_MINUTES=330
```
Save with Ctrl+O, Enter, Ctrl+X.

## 7. Start it
```bash
docker compose up -d --build
docker compose ps
curl http://localhost/health        # {"status":"ok"}
```
Open `http://<ELASTIC_IP>` in your browser and create your account. To load the Dev Shah demo account (`dev.shah@prepledger.local` / `DevShah@2026`) with sample data, run `docker compose exec web python seed.py`.

Once your own account exists, set `ALLOW_REGISTRATION=false` in `.env` and run `docker compose up -d` so strangers cannot sign up on your server. (Leave it `true` if you want to share the app with classmates.)

## 8. HTTPS with a domain (recommended)
Browsers show "not secure" for plain HTTP, and your password would travel unencrypted. To fix it:
1. Get a domain (Route 53 or any registrar) and create an **A record**: `prep.yourdomain.com` → your Elastic IP.
2. Edit `deploy/Caddyfile`: change `:80 {` to `prep.yourdomain.com {`.
3. `docker compose up -d`. Caddy requests a free certificate automatically; wait a minute, then open `https://prep.yourdomain.com`.

## 9. Daily backup to S3
```bash
cd ~/prepledger
BUCKET=prepledger-yourname-backups ./deploy/backup.sh      # test it once; check the file in S3
crontab -e
```
Add this line to run it every night at 2 AM server time:
```
0 2 * * * cd /home/ec2-user/prepledger && BUCKET=prepledger-yourname-backups ./deploy/backup.sh >> /tmp/backup.log 2>&1
```
To restore, copy the file from S3, stop the app (`docker compose down`), put it back as `/data/prepledger.db` inside the volume and start again.

## 10. Updating the app later
```bash
# upload the new zip, unzip over the old folder, then:
docker compose up -d --build
```
Your data is in a Docker volume and survives rebuilds.

Useful commands: `docker compose logs -f web` (live logs), `docker compose ps` (status), `docker compose restart web`.

## 11. Shut it down to avoid charges
Terminate the instance, **release the Elastic IP** (an unattached one is billed), and delete the S3 backups when you no longer need them.

## Troubleshooting
| Problem | Fix |
|---|---|
| Page does not open | Security group must allow 80 and 443; run `docker compose ps` |
| `permission denied` for docker | Log out and back in after `usermod -aG docker` |
| `Permission denied (publickey)` on ssh | Use the right `.pem`, `chmod 400`, user is `ec2-user` |
| HTTPS certificate not issued | The A record must point to the Elastic IP, ports 80 and 443 must be open |
| Backup says `Unable to locate credentials` | The IAM role is not attached: EC2 → Actions → Security → Modify IAM role |
| Dates are a day off | Change `TZ_OFFSET_MINUTES` in `.env` and restart |
| Out of memory | Add 1 GB swap: `sudo dd if=/dev/zero of=/swapfile bs=1M count=1024 && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |

## Upgrade ideas (good interview talking points)
1. Move SQLite to **RDS PostgreSQL** and run the container on **ECS Fargate** behind an **Application Load Balancer**.
2. Email reminders for due reviews and interview dates using **SES** and an **EventBridge** schedule.
3. Infrastructure as code with **Terraform**, and a **GitHub Actions** pipeline that builds, pushes to **ECR** and deploys.
