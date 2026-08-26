## IAM is a global service; both roles are created with the default provider.
## No provider alias is needed — both Lambda functions run in ap-southeast-2.

## Role 1 — Processor Lambda (ap-southeast-2; calls Textract in ap-southeast-2)

resource "aws_iam_role" "lambda_processor" {
  name = "${var.project_name}-processor-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "lambda_processor" {
  name = "${var.project_name}-processor-policy"
  role = aws_iam_role.lambda_processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.aws_account_id}:*"
      },
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.image_jobs.arn
      },
      {
        Sid    = "S3GetUpload"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.uploads.arn}/uploads/*"
      },
      {
        Sid    = "S3GetCropped"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = "${aws_s3_bucket.uploads.arn}/cropped/*"
      },
      {
        Sid    = "S3CroppedAndDebugWrite"
        Effect = "Allow"
        Action = "s3:PutObject"
        Resource = [
          "${aws_s3_bucket.uploads.arn}/debug/*",
          "${aws_s3_bucket.uploads.arn}/cropped/*",
        ]
      },
      {
        Sid      = "TextractDetect"
        Effect   = "Allow"
        Action   = "textract:DetectDocumentText"
        Resource = "*"
      },
      {
        # Inference profiles (cross-region) use a different ARN format to foundation models
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = "bedrock:InvokeModel"
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${var.primary_region}:${var.aws_account_id}:inference-profile/*",
        ]
      },
      {
        # Required by Bedrock to verify/complete Anthropic Marketplace subscription
        Sid      = "MarketplaceSubscription"
        Effect   = "Allow"
        Action   = ["aws-marketplace:ViewSubscriptions", "aws-marketplace:Subscribe"]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBWrite"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
        Resource = aws_dynamodb_table.jobs.arn
      },
      {
        Sid    = "LineItemsWrite"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:BatchWriteItem"]
        Resource = aws_dynamodb_table.line_items.arn
      },
      {
        Sid    = "ImageHashesReadWrite"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.image_hashes.arn
      },
    ]
  })
}

## Role 2 — API Lambda (ap-southeast-2; DynamoDB + presigned URL generation)

resource "aws_iam_role" "lambda_api" {
  name = "${var.project_name}-api-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "lambda_api" {
  name = "${var.project_name}-api-policy"
  role = aws_iam_role.lambda_api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:${var.aws_account_id}:*"
      },
      {
        Sid    = "DynamoDBReadWrite"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:TransactWriteItems"]
        Resource = [
          aws_dynamodb_table.jobs.arn,
          "${aws_dynamodb_table.jobs.arn}/index/*",
        ]
      },
      {
        Sid    = "ImageHashesDelete"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:DeleteItem", "dynamodb:TransactWriteItems"]
        Resource = aws_dynamodb_table.image_hashes.arn
      },
      {
        Sid    = "LineItemsAccess"
        Effect = "Allow"
        Action = ["dynamodb:Query", "dynamodb:BatchWriteItem", "dynamodb:UpdateItem"]
        Resource = [
          aws_dynamodb_table.line_items.arn,
          "${aws_dynamodb_table.line_items.arn}/index/*",
        ]
      },
      {
        # PutObject is required to generate presigned PUT URLs — the signing role
        # must have the same permission as the presigned URL will grant
        Sid      = "S3PresignedPut"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.uploads.arn}/uploads/*"
      },
      {
        # GetObject is required to generate presigned GET URLs for debug and cropped image downloads
        Sid    = "S3DebugAndCroppedRead"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.uploads.arn}/debug/*",
          "${aws_s3_bucket.uploads.arn}/cropped/*",
        ]
      },
      {
        # DeleteObject is required to clean up all S3 objects when a receipt is deleted
        Sid    = "S3DeleteReceipt"
        Effect = "Allow"
        Action = "s3:DeleteObject"
        Resource = [
          "${aws_s3_bucket.uploads.arn}/uploads/*",
          "${aws_s3_bucket.uploads.arn}/debug/*",
          "${aws_s3_bucket.uploads.arn}/cropped/*",
        ]
      },
    ]
  })
}
