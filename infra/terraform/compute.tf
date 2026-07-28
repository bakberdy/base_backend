data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["137112412989"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

resource "aws_key_pair" "backend" {
  count = var.ssh_public_key == null ? 0 : 1

  key_name   = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "backend" {
  for_each = local.environments

  ami                         = coalesce(var.ami_id, data.aws_ami.amazon_linux_2023.id)
  instance_type               = each.value.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.backend[each.key].id]
  iam_instance_profile        = aws_iam_instance_profile.backend.name
  key_name                    = local.ec2_key_name
  associate_public_ip_address = true
  monitoring                  = false
  source_dest_check           = true
  disable_api_stop            = each.value.disable_api_stop
  disable_api_termination     = each.value.disable_api_termination

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    delete_on_termination = true
    encrypted             = var.root_volume_encrypted
    volume_size           = each.value.root_volume_size
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
  }

  tags = {
    Name = "${var.project_name}-${each.key}"
  }

  lifecycle {
    ignore_changes = [
      ami,
      user_data,
      user_data_replace_on_change,
    ]
  }
}

resource "aws_eip" "backend" {
  for_each = local.environments

  domain   = "vpc"
  instance = aws_instance.backend[each.key].id

  tags = {
    Name = each.value.eip_name
  }
}

resource "aws_route53_record" "backend" {
  for_each = var.route53_zone_id == null ? {} : var.environment_domains

  zone_id = var.route53_zone_id
  name    = each.value
  type    = "A"
  ttl     = 300
  records = [aws_eip.backend[each.key].public_ip]
}
