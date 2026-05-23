output "ec2_public_ip" {
  description = "Current public IP assigned to the EC2 instance."
  value       = aws_instance.app.public_ip
}

output "elastic_ip" {
  description = "Static Elastic IP associated with the EC2 instance."
  value       = aws_eip.app.public_ip
}

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.app.id
}

output "ssh_connection_command" {
  description = "SSH command for connecting to the instance."
  value       = "ssh -i <path-to-private-key> ec2-user@${aws_eip.app.public_ip}"
}

output "domain_setup_instructions" {
  description = "DNS instructions for routing a domain to this MVP host."
  value       = var.domain_name != "" ? "Create or update an A record for ${var.domain_name} pointing to ${aws_eip.app.public_ip}." : "Set domain_name and create an A record pointing to ${aws_eip.app.public_ip}, or use the Elastic IP directly."
}
