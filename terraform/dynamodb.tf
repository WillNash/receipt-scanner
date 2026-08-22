resource "aws_dynamodb_table" "image_hashes" {
  name         = "${var.project_name}-image-hashes"
  billing_mode = "PAY_PER_REQUEST"

  key_schema {
    attribute_name = "user_id"
    key_type       = "HASH"
  }

  key_schema {
    attribute_name = "image_hash"
    key_type       = "RANGE"
  }

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

  # item_sk  = "{created_at}#{job_id}#{NNN}"  — sortable by date, unique per item
  # desc_created = "{description}#{created_at}" — GSI SK for per-item date queries
  key_schema {
    attribute_name = "user_id"
    key_type       = "HASH"
  }

  key_schema {
    attribute_name = "item_sk"
    key_type       = "RANGE"
  }

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
    projection_type = "ALL"

    key_schema {
      attribute_name = "user_id"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "desc_created"
      key_type       = "RANGE"
    }
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

  # Only key attributes are declared here; non-key attributes (status, label, etc.)
  # are schema-free and must NOT appear in attribute blocks
  key_schema {
    attribute_name = "job_id"
    key_type       = "HASH"
  }

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
    projection_type = "ALL"

    key_schema {
      attribute_name = "user_id"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "created_at"
      key_type       = "RANGE"
    }
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
