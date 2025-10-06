# app/tags.py
"""
Preset tags system for ADHD-friendly ticket categorization.
Provides predefined tag options to make categorization faster and more consistent.
"""

import json
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default preset tags - can be overridden by config file
DEFAULT_PRESET_TAGS = [
    {"label": "Work", "value": "work", "color": "#3b82f6"},  # blue
    {"label": "Personal", "value": "personal", "color": "#10b981"},  # green
    {"label": "Urgent", "value": "urgent", "color": "#ef4444"},  # red
    {"label": "Shopping", "value": "shopping", "color": "#f59e0b"},  # yellow
    {"label": "Health", "value": "health", "color": "#ec4899"},  # pink
    {"label": "Home", "value": "home", "color": "#8b5cf6"},  # purple
    {"label": "Bills", "value": "bills", "color": "#f97316"},  # orange
    {"label": "Ideas", "value": "ideas", "color": "#06b6d4"},  # cyan
]

CONFIG_FILE = Path("app/config/tags.json")

def load_preset_tags() -> List[Dict[str, str]]:
    """Load preset tags from config file, fallback to defaults."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                preset_tags = config.get('preset_tags', DEFAULT_PRESET_TAGS)
                logger.info(f"TAGS: Loaded {len(preset_tags)} preset tags from config")
                return preset_tags
        else:
            logger.info(f"TAGS: Config file not found, using {len(DEFAULT_PRESET_TAGS)} default tags")
            return DEFAULT_PRESET_TAGS
    except Exception as e:
        logger.warning(f"TAGS: Error loading config, using defaults: {e}")
        return DEFAULT_PRESET_TAGS

def save_preset_tags(tags: List[Dict[str, str]]) -> bool:
    """Save preset tags to config file."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = {"preset_tags": tags}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"TAGS: Saved {len(tags)} preset tags to config")
        return True
    except Exception as e:
        logger.error(f"TAGS: Error saving config: {e}")
        return False

def get_preset_tags() -> List[Dict[str, str]]:
    """Get current preset tags for UI rendering."""
    return load_preset_tags()

def validate_tag_config(tags: List[Dict[str, str]]) -> bool:
    """Validate tag configuration format."""
    if not isinstance(tags, list):
        return False
    
    for tag in tags:
        if not isinstance(tag, dict):
            return False
        if not all(key in tag for key in ['label', 'value', 'color']):
            return False
        if not all(isinstance(tag[key], str) for key in ['label', 'value', 'color']):
            return False
    
    return True