import {
  for_each = var.existing_resource_ids == null ? {} : { current = var.existing_resource_ids.vpc_id }
  to       = aws_vpc.backend
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = var.existing_resource_ids.internet_gateway_id }
  to       = aws_internet_gateway.backend
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = var.existing_resource_ids.subnet_id }
  to       = aws_subnet.public
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = var.existing_resource_ids.route_table_id }
  to       = aws_route_table.public
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : {
    current = "${var.existing_resource_ids.subnet_id}/${var.existing_resource_ids.route_table_id}"
  }
  to = aws_route_table_association.public
  id = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : var.existing_resource_ids.security_group_ids
  to       = aws_security_group.backend[each.key]
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : var.existing_resource_ids.instance_ids
  to       = aws_instance.backend[each.key]
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : var.existing_resource_ids.eip_allocation_ids
  to       = aws_eip.backend[each.key]
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = local.ec2_instance_role_name }
  to       = aws_iam_role.ec2
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = local.ec2_instance_role_name }
  to       = aws_iam_instance_profile.backend
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : {
    current = "${local.ec2_instance_role_name}/arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }
  to = aws_iam_role_policy_attachment.ec2_ssm
  id = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : { current = local.github_deploy_role_name }
  to       = aws_iam_role.github_deploy
  id       = each.value
}

import {
  for_each = var.existing_resource_ids == null ? {} : {
    current = "${local.github_deploy_role_name}:${local.github_deploy_role_name}Policy"
  }
  to = aws_iam_role_policy.github_deploy
  id = each.value
}

import {
  for_each = var.manage_github_configuration && var.adopt_existing_github_configuration ? { current = var.github_repository } : {}
  to       = github_actions_repository_permissions.backend[0]
  id       = each.value
}

import {
  for_each = var.manage_github_configuration && var.adopt_existing_github_configuration ? local.environments : {}
  to       = github_repository_environment.backend[each.key]
  id       = "${var.github_repository}:${each.key}"
}

import {
  for_each = var.manage_github_configuration && var.adopt_existing_github_configuration ? local.environments : {}
  to       = github_actions_environment_variable.instance_id[each.key]
  id       = "${var.github_repository}:${each.key}:EC2_INSTANCE_ID"
}

import {
  for_each = var.manage_github_configuration && var.adopt_existing_github_configuration ? var.existing_github_repository_variables : []
  to       = github_actions_variable.repository[each.key]
  id       = "${var.github_repository}:${each.key}"
}

import {
  for_each = var.manage_github_configuration && var.adopt_existing_github_configuration ? { current = var.github_repository } : {}
  to       = github_actions_secret.deploy_role[0]
  id       = "${each.value}:AWS_ROLE_TO_ASSUME"
}
