resource "aws_dynamodb_table" "ews_bruteforceblocker" {
  name         = "${lower(var.app_env)}_ews_bruteforceblocker"
  billing_mode = "PAY_PER_REQUEST"
  table_class  = "STANDARD"

  server_side_encryption {
    enabled = true
  }

  attribute {
    name = "address_id"
    type = "S"
  }

  hash_key = "address_id"
  tags     = local.tags
}
