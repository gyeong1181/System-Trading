locals {
  strategy_images_ready = (
    (var.enable_psar_container ? var.psar_rsi_image != "" : true) &&
    (var.enable_okx_qqq_container ? var.okx_qqq_image != "" : true) &&
    (var.enable_okx_xau_container ? var.okx_xau_image != "" : true)
  )
  psar_rsi_image_value  = var.psar_rsi_image != "" ? var.psar_rsi_image : "REPLACE_ME_PSAR_RSI_IMAGE"
  okx_qqq_image_value   = var.okx_qqq_image != "" ? var.okx_qqq_image : "REPLACE_ME_OKX_QQQ_IMAGE"
  okx_xau_image_value   = var.okx_xau_image != "" ? var.okx_xau_image : "REPLACE_ME_OKX_XAU_IMAGE"

  common_tags = merge(
    {
      Project   = var.project_name
      ManagedBy = "Terraform"
      Service   = "trading-executor"
    },
    var.extra_tags
  )
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_security_group" "this" {
  name_prefix = "${var.project_name}-"
  description = "Security group for the PSAR RSI trading executor."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  ingress {
    description = "Webhook HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.http_allowed_cidrs
  }

  dynamic "ingress" {
    for_each = var.enable_monitoring_ports ? {
      for port in var.monitoring_ports : tostring(port) => port
    } : {}
    content {
      description = "Monitoring ${ingress.value}"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = var.monitoring_allowed_cidrs
    }
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ec2" {
  name_prefix        = "${var.project_name}-ec2-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "ssm_parameter_read" {
  statement {
    sid    = "ReadTradingParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
      "ssm:DescribeParameters"
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_parameter_prefix}*"
    ]
  }

  statement {
    sid    = "DecryptSecureParameters"
    effect = "Allow"
    actions = [
      "kms:Decrypt"
    ]
    resources = var.ssm_kms_key_arn != "" ? [var.ssm_kms_key_arn] : ["*"]
  }
}

resource "aws_iam_role_policy" "ssm_parameter_read" {
  name_prefix = "${var.project_name}-ssm-params-"
  role        = aws_iam_role.ec2.id
  policy      = data.aws_iam_policy_document.ssm_parameter_read.json
}

resource "aws_iam_instance_profile" "ec2" {
  name_prefix = "${var.project_name}-"
  role        = aws_iam_role.ec2.name
  tags        = local.common_tags
}

resource "aws_instance" "this" {
  ami                    = data.aws_ssm_parameter.al2023_ami.value
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id != "" ? var.subnet_id : data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.this.id]
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    project_name          = var.project_name
    app_user              = var.app_user
    strategy_stack_dir    = var.strategy_stack_dir
    deploy_strategy_stack = var.deploy_strategy_stack
    strategy_images_ready = local.strategy_images_ready
    strategy_compose = templatefile("${path.module}/docker-compose.strategies.yml.tftpl", {
      enable_psar_container   = var.enable_psar_container
      enable_okx_qqq_container = var.enable_okx_qqq_container
      enable_okx_xau_container = var.enable_okx_xau_container
      psar_rsi_image          = local.psar_rsi_image_value
      okx_qqq_image           = local.okx_qqq_image_value
      okx_xau_image           = local.okx_xau_image_value
      psar_rsi_container_port = var.psar_rsi_container_port
    })
    strategy_service = templatefile("${path.module}/trading-strategy-stack.service.tftpl", {
      strategy_stack_dir = var.strategy_stack_dir
    })
    env_sync_script = templatefile("${path.module}/sync-env-from-ssm.sh.tftpl", {
      use_ssm_env          = var.use_ssm_env
      ssm_parameter_prefix = var.ssm_parameter_prefix
      aws_region           = var.aws_region
      strategy_stack_dir   = var.strategy_stack_dir
      app_user             = var.app_user
    })
    env_sync_service = templatefile("${path.module}/trading-env-sync.service.tftpl", {
      strategy_stack_dir = var.strategy_stack_dir
    })
  })

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-ec2"
    }
  )
}

resource "aws_eip" "this" {
  count    = var.allocate_eip ? 1 : 0
  instance = aws_instance.this.id
  domain   = "vpc"

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-eip"
    }
  )
}
