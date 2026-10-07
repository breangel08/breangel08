from .custom_web import CustomWebAdapter


def get_adapter(target):
    if target == "CUSTOM_WEB":
        return CustomWebAdapter()
    if target == "SHOPIFY":
        from .shopify import ShopifyAdapter
        return ShopifyAdapter()
    raise ValueError("Webflow production integration is not configured. Design review and project memory remain available; production is blocked rather than relabeled as a native Webflow build.")
