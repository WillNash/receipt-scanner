resource "aws_dynamodb_table" "image_hashes" {
  name         = "${var.project_name}-image-hashes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "image_hash"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "image_hash"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "line_items" {
  name         = "${var.project_name}-line-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "item_sk"

  # item_sk  = "{created_at}#{job_id}#{NNN}"  — sortable by date, unique per item
  # desc_created = "{description}#{created_at}" — GSI SK for per-item date queries
  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "item_sk"
    type = "S"
  }

  attribute {
    name = "desc_created"
    type = "S"
  }

  global_secondary_index {
    name            = "description-date-index"
    hash_key        = "user_id"
    range_key       = "desc_created"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "stores" {
  name         = "${var.project_name}-stores"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "store_id"

  attribute {
    name = "store_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "jobs" {
  name         = "${var.project_name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  # Only key attributes are declared here; non-key attributes (status, label, etc.)
  # are schema-free and must NOT appear in attribute blocks
  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "user-jobs-index"
    hash_key        = "user_id"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
