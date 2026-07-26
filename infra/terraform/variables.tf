variable "project" {
  description = "Resource name prefix"
  type        = string
  default     = "baltic-bridge"
}

variable "region" {
  description = "AWS region — eu-north-1 (Stockholm) for GDPR data residency"
  type        = string
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  description = "CIDR for the dedicated VPC"
  type        = string
  default     = "10.80.0.0/24"
}

variable "instance_type" {
  description = "EC2 instance type (arm64/Graviton). t4g.medium fits app + Postgres + MinIO for the first 50 suppliers."
  type        = string
  default     = "t4g.medium"
}

variable "root_volume_gb" {
  description = "Root volume size (OS only — all state lives on the data volume)"
  type        = number
  default     = 20
}

variable "data_volume_gb" {
  description = "Dedicated gp3 volume mounted at /var/lib/docker (pgdata + miniodata live here; snapshotted daily by DLM)"
  type        = number
  default     = 50
}

variable "admin_ssh_cidr" {
  description = "CIDR allowed to SSH (port 22). Empty = no SSH at all; use SSM Session Manager instead (recommended)."
  type        = string
  default     = ""
}

variable "alarm_email" {
  description = "Email for CloudWatch alarm notifications. Empty = no SNS topic."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Hosted zone ID for DNS records. Empty = manage DNS elsewhere."
  type        = string
  default     = ""
}

variable "app_domain" {
  description = "Public app hostname (PUBLIC_BASE_URL), e.g. www.example.com"
  type        = string
  default     = ""
}

variable "files_domain" {
  description = "Public MinIO hostname for presigned URLs (S3_ENDPOINT), e.g. files.example.com"
  type        = string
  default     = ""
}

variable "backup_expire_days" {
  description = "Days to keep nightly pg_dump objects in the backup bucket"
  type        = number
  default     = 35
}

variable "snapshot_retain_count" {
  description = "Daily EBS snapshots of the data volume to retain (DLM)"
  type        = number
  default     = 14
}
