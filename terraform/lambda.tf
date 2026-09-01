## Lambda packaging via archive provider — zips pre-built package/ directories

data "archive_file" "processor_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/processor/package"
  output_path = "${path.module}/../lambda/processor/processor.zip"
}

data "archive_file" "api_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/api/package"
  output_path = "${path.module}/../lambda/api/api.zip"
}

## Processor zip uploaded via S3 — direct Lambda upload is capped at ~70 MB;
## the processor zip exceeds that limit once opencv-python-headless is included.

resource "aws_s3_object" "processor_zip" {
  bucket = aws_s3_bucket.deployments.id
  key    = "lambda/processor.zip"
  source = data.archive_file.processor_zip.output_path
  etag   = data.archive_file.processor_zip.output_md5
}

## Processor Lambda — runs in ap-southeast-2; calls Textract in the same region

resource "aws_lambda_function" "bedrock_processor" {
  function_name    = "${var.project_name}-processor"
  s3_bucket        = aws_s3_bucket.deployments.id
  s3_key           = aws_s3_object.processor_zip.key
  source_code_hash = data.archive_file.processor_zip.output_base64sha256
  role             = aws_iam_role.lambda_processor.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_processor
  memory_size      = 512

  environment {
    variables = {
      DYNAMODB_TABLE     = aws_dynamodb_table.jobs.name
      LINE_ITEMS_TABLE   = aws_dynamodb_table.line_items.name
      IMAGE_HASHES_TABLE = aws_dynamodb_table.image_hashes.name
      STORES_TABLE       = aws_dynamodb_table.stores.name
      S3_UPLOADS_BUCKET  = aws_s3_bucket.uploads.bucket
      PRIMARY_REGION     = var.primary_region
      BEDROCK_MODEL_ID   = var.bedrock_model_id
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

## SQS → Processor event source mapping (both in ap-southeast-2 — no cross-region ESM)

resource "aws_lambda_event_source_mapping" "sqs_to_processor" {
  event_source_arn        = aws_sqs_queue.image_jobs.arn
  function_name           = aws_lambda_function.bedrock_processor.arn
  batch_size              = 1
  enabled                 = true
  function_response_types = ["ReportBatchItemFailures"]
}

## API Lambda — presigned URL generation + job status polling

resource "aws_lambda_function" "api_handler" {
  function_name    = "${var.project_name}-api"
  filename         = data.archive_file.api_zip.output_path
  source_code_hash = data.archive_file.api_zip.output_base64sha256
  role             = aws_iam_role.lambda_api.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_api
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE       = aws_dynamodb_table.jobs.name
      LINE_ITEMS_TABLE     = aws_dynamodb_table.line_items.name
      IMAGE_HASHES_TABLE   = aws_dynamodb_table.image_hashes.name
      STORES_TABLE         = aws_dynamodb_table.stores.name
      UPLOADS_BUCKET       = aws_s3_bucket.uploads.bucket
      COGNITO_USER_POOL_ID  = aws_cognito_user_pool.main.id
      COGNITO_APP_CLIENT_ID = aws_cognito_user_pool_client.main.id
      PRIMARY_REGION        = var.primary_region
      ALLOWED_ORIGIN       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
      DAILY_UPLOAD_LIMIT   = var.daily_upload_limit
      GLOBAL_UPLOAD_LIMIT  = var.global_upload_limit
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

## Stores refresh Lambda — weekly Overpass scrape → DynamoDB

data "archive_file" "stores_refresh_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/stores_refresh/package"
  output_path = "${path.module}/../lambda/stores_refresh/stores_refresh.zip"
}

resource "aws_cloudwatch_log_group" "stores_refresh" {
  name              = "/aws/lambda/${var.project_name}-stores-refresh"
  retention_in_days = 14

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_lambda_function" "stores_refresh" {
  function_name    = "${var.project_name}-stores-refresh"
  filename         = data.archive_file.stores_refresh_zip.output_path
  source_code_hash = data.archive_file.stores_refresh_zip.output_base64sha256
  role             = aws_iam_role.lambda_stores_refresh.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 128

  environment {
    variables = {
      STORES_TABLE   = aws_dynamodb_table.stores.name
      PRIMARY_REGION = var.primary_region
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_rule" "stores_refresh_weekly" {
  name                = "${var.project_name}-stores-refresh-weekly"
  description         = "Trigger stores refresh every Monday at midnight UTC"
  schedule_expression = "cron(0 0 ? * MON *)"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "stores_refresh" {
  rule      = aws_cloudwatch_event_rule.stores_refresh_weekly.name
  target_id = "stores-refresh-lambda"
  arn       = aws_lambda_function.stores_refresh.arn
}

resource "aws_lambda_permission" "stores_refresh_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stores_refresh.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stores_refresh_weekly.arn
}

## Allow API Gateway to invoke the API Lambda

resource "aws_lambda_permission" "api_handler_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}
