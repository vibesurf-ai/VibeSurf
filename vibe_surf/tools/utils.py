from bs4 import BeautifulSoup
from browser_use.dom.service import EnhancedDOMTreeNode

def clean_html_basic(page_html_content, max_text_length=100):
    soup = BeautifulSoup(page_html_content, 'html.parser')

    for script in soup(["script", "style"]):
        script.decompose()

    from bs4 import Comment
    comments = soup.findAll(text=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()

    for text_node in soup.find_all(string=True):
        if text_node.parent.name not in ['script', 'style']:
            clean_text = ' '.join(text_node.split())

            if len(clean_text) > max_text_length:
                clean_text = clean_text[:max_text_length].rstrip() + "..."

            if clean_text != text_node:
                text_node.replace_with(clean_text)

    important_attrs = ['id', 'class', 'name', 'role', 'type',
                       'colspan', 'rowspan', 'headers', 'scope',
                       'href', 'src', 'alt', 'title']

    for tag in soup.find_all():
        attrs_to_keep = {}
        for attr in list(tag.attrs.keys()):
            if (attr in important_attrs or
                    attr.startswith('data-') or
                    attr.startswith('aria-')):
                attrs_to_keep[attr] = tag.attrs[attr]
        tag.attrs = attrs_to_keep

    return str(soup)


def get_sibling_position(node: EnhancedDOMTreeNode) -> int:
    """Get the position of node among its siblings with the same tag"""
    if not node.parent_node:
        return 1

    tag_name = node.tag_name
    position = 1

    # Find siblings with same tag name before this node
    for sibling in node.parent_node.children:
        if sibling == node:
            break
        if sibling.tag_name == tag_name:
            position += 1

    return position


def extract_css_hints(node: EnhancedDOMTreeNode) -> dict:
    """Extract CSS selector construction hints"""
    hints = {}

    if "id" in node.attributes:
        hints["id"] = f"#{node.attributes['id']}"

    if "class" in node.attributes:
        classes = node.attributes["class"].split()
        hints["class"] = f".{'.'.join(classes[:3])}"  # Limit class count

    # Attribute selector hints
    for attr in ["name", "data-testid", "type"]:
        if attr in node.attributes:
            hints[f"attr_{attr}"] = f"[{attr}='{node.attributes[attr]}']"

    return hints


def convert_selector_map_for_llm(selector_map) -> dict:
    """
    Convert complex selector_map to simplified format suitable for LLM understanding and JS code writing
    """
    simplified_elements = []

    for element_index, node in selector_map.items():
        if node.is_visible and node.element_index is not None:  # Only include visible interactive elements
            element_info = {
                "tag": node.tag_name,
                "text": node.get_meaningful_text_for_llm()[:200],  # Limit text length

                # Selector information - most needed for JS code
                "selectors": {
                    "xpath": node.xpath,
                    "css_hints": extract_css_hints(node),  # Extract id, class etc
                },

                # Element semantics
                "role": node.ax_node.role if node.ax_node else None,
                "type": node.attributes.get("type"),
                "aria_label": node.attributes.get("aria-label"),

                # Key attributes
                "attributes": {k: v for k, v in node.attributes.items()
                               if k in ["id", "class", "name", "href", "src", "value", "placeholder", "data-testid"]},

                # Interactivity
                "is_clickable": node.snapshot_node.is_clickable if node.snapshot_node else False,
                "is_input": node.tag_name.lower() in ["input", "textarea", "select"],

                # Structure information
                "parent_tag": node.parent_node.tag_name if node.parent_node else None,
                "position_info": f"{node.tag_name}[{get_sibling_position(node)}]"
            }
            simplified_elements.append(element_info)

    return {
        "page_elements": simplified_elements,
        "total_elements": len(simplified_elements)
    }