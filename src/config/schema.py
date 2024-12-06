CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "database": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "name": {"type": "string"},
                "user": {"type": "string"},
                "password": {"type": "string"}
            },
            "required": ["host", "port", "name", "user", "password"]
        },
        "api": {
            "type": "object",
            "properties": {
                "etherscan": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"}
                    },
                    "required": ["key"]
                },
                "openai": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "model": {"type": "string"}
                    },
                    "required": ["key"]
                }
            }
        },
        "github": {
            "type": "object",
            "properties": {
                "api_token": {"type": "string"},
                "poll_interval": {"type": "integer", "default": 300}
            }
        },
        "watchers": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "webhook_port": {"type": "integer", "default": 8080},
                "active_watchers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": []
                }
            }
        },
        "data_dir": {"type": "string"}
    },
    "required": ["database", "data_dir"]
} 