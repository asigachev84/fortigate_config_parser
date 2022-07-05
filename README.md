# Parse Fortigate Firewall Config into Nested Dictionary

### Usage:
```
_import fg_config_parser as fgp_

parsed_config, vdom_list = fgp.parse_config(cfg_text)
```

```parse_config``` function returns config as nested dictionary and VDOM list.
If firewall is in single-VDOM mode all config will be under _'global'_ dictionary key