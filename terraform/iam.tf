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
        Sid      = "S3GetUpload"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        # AnalyzeDocument does not support resource-level restrictions
        Sid      = "TextractAnalyzeDocument"
        Effect   = "Allow"
        Action   = "textract:AnalyzeDocument"
        Resource = "*"
      },
      {
        Sid      = "S3DebugWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.uploads.arn}/debug/*"
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
        Action = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.line_items.arn
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
        Action = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem"]
        Resource = [
          aws_dynamodb_table.jobs.arn,
          "${aws_dynamodb_table.jobs.arn}/index/*",
        ]
      },
      {
        # PutObject is required to generate presigned PUT URLs — the signing role
        # must have the same permission as the presigned URL will grant
        Sid      = "S3PresignedPut"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        # GetObject is required to generate presigned GET URLs for debug downloads
        Sid      = "S3DebugRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.uploads.arn}/debug/*"
      },
    ]
  })
}
