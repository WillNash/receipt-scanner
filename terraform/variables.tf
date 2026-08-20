variable "project_name" {
  type    = string
  default = "bedrock-image-ai"
}

variable "primary_region" {
  type    = string
  default = "ap-southeast-2"
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID — auto-written by scripts/install_tools.sh setup step"
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique Cognito hosted UI domain prefix (e.g. bedrock-image-ai-123456)"
}

variable "environment" {
  type    = string
  default = "demo"
}

variable "lambda_timeout_processor" {
  type    = number
  default = 120
}

variable "lambda_timeout_api" {
  type    = number
  default = 30
}

variable "daily_upload_limit" {
  type    = number
  default = 50
}

variable "global_upload_limit" {
  type    = number
  default = 100
}

variable "bedrock_model_id" {
  type    = string
  default = "amazon.nova-lite-v1:0"
}
