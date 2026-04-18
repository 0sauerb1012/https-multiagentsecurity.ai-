resource "aws_cloudwatch_event_rule" "this" {
  name                = "${var.name_prefix}-ingestion-schedule"
  description         = "Scheduled trigger for ingestion pipeline"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.this.name
  target_id = "ingestion-lambda"
  arn       = var.lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}
