resource "aws_sqs_queue" "image_jobs_dlq" {
  name                      = "${var.project_name}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days for DLQ inspection

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "image_jobs" {
  name = "${var.project_name}-jobs"

  # Must be >= Lambda timeout. Use 6× the processor timeout (6 × 60s = 360s).
  # The researcher example shows 300s which is arithmetically wrong — use 360s.
  visibility_timeout_seconds = 360
  message_retention_seconds  = 86400 # 1 day

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.image_jobs_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_sqs_queue_policy" "image_jobs" {
  queue_url = aws_sqs_queue.image_jobs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.image_jobs.arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = aws_s3_bucket.uploads.arn
        }
      }
    }]
  })
}
