output "cloudfront_domain" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_invoke_url" {
  value = aws_api_gateway_stage.main.invoke_url
}

output "cognito_base_url" {
  description = "Cognito hosted UI base URL — used by inject_config.py to construct login and token URLs"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.primary_region}.amazoncognito.com"
}

output "cognito_login_url" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.primary_region}.amazoncognito.com/login?client_id=${aws_cognito_user_pool_client.main.id}&response_type=code&scope=email+openid+profile&redirect_uri=https://${aws_cloudfront_distribution.frontend.domain_name}/callback"
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.main.id
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "uploads_bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}

output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.bucket
}

output "primary_region" {
  value = var.primary_region
}
