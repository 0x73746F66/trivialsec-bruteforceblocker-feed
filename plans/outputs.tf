output "feed_processor_bruteforceblocker_arn" {
  value = aws_lambda_function.feed_processor_bruteforceblocker.arn
}
output "feed_processor_bruteforceblocker_role" {
  value = aws_iam_role.feed_processor_bruteforceblocker_role.name
}
output "feed_processor_bruteforceblocker_role_arn" {
  value = aws_iam_role.feed_processor_bruteforceblocker_role.arn
}
output "feed_processor_bruteforceblocker_policy_arn" {
  value = aws_iam_policy.feed_processor_bruteforceblocker_policy.arn
}
