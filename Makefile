.PHONY: setup package plan apply deploy smoke destroy

TERRAFORM_DIR = terraform
SCRIPTS_DIR   = scripts

setup:
	@echo "Run scripts/install_tools.sh to install Terraform, AWS CLI, and pip dependencies."
	@echo "Then set AWS credentials and run: make deploy"

package:
	bash $(SCRIPTS_DIR)/package_lambdas.sh

plan: package
	terraform -chdir=$(TERRAFORM_DIR) init -upgrade
	terraform -chdir=$(TERRAFORM_DIR) plan -var-file=terraform.tfvars

apply: package
	terraform -chdir=$(TERRAFORM_DIR) init -upgrade
	terraform -chdir=$(TERRAFORM_DIR) apply -var-file=terraform.tfvars -auto-approve

deploy: apply
	python3 $(SCRIPTS_DIR)/inject_config.py

smoke:
	python3 $(SCRIPTS_DIR)/smoke_test.py

destroy:
	terraform -chdir=$(TERRAFORM_DIR) destroy -var-file=terraform.tfvars -auto-approve
