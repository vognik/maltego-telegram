from maltego_trx.decorator_registry import TransformRegistry

registry = TransformRegistry(
    owner="vognik",
    author="vognik",
    host_url="https://transforms.acme.org",
    seed_ids=["demo"],
)

# The rest of these attributes are optional

# metadata
registry.version = "0.1"

# global settings
# from settings import api_id_setting, api_hash_setting
# registry.global_settings = [api_id_setting, api_hash_setting]

# transform suffix to indicate datasource
# registry.display_name_suffix = " [ACME]"

# reference OAuth settings
# registry.oauth_settings_id = ['github-oauth']
