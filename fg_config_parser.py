# Module that parses Fortigate config into nested dictionary
# ==========================================================
#
# Usage:
#
# import fg_config_parser as fgp
#
# parsed_config, vdom_list = fgp.parse_config(cfg_text)
#
# parse_config function returns config as nested dictionary and VDOM list.
# If firewall is in single-VDOM mode all config will be under 'global' dictionary key


import re


list_set_params = {
    'system accprofile': ['vdom'],
    'wanopt content-delivery-network-rule': ['host-domain-name-suffix'],
    'system ntp': ['interface'],
    'system automation-stitch': ['action',
                                 'email-to'],
    'system dhcp server': ['vci-string'],
    'firewall addrgrp': ['member'],
    'switch-controller managed-switch': ['allowed-vlans'],
    'firewall policy': ['dstintf',
                        'dstaddr',
                        'interface',
                        'internet-service-name',
                        'fsso-groups',
                        'groups',
                        'service',
                        'srcaddr',
                        'srcintf'],
    'system zone': ['interface'],
    'wireless-controller wtp-profile': ['channel'],
    'router ospf': ['passive-interface'],
    'system admin': ['gui-vdom-menu-favorites'],
    'system ha': ['monitor'],
    'vpn ssl web portal': ['split-tunneling-routing-address'],
    'vpn ssl settings': ['tunnel-ip-pools', 'source-interface', 'source-address'],
    'system sdwan': ['server', 'members', 'src', 'dst'],
    'file-filter profile': ['filetype'],
    'firewall vipgrp': ['member'],
    'firewall service group': ['member']
}


def get_vdom_list(_cfg_text):
    _vdom_list = re.findall(r'edit (.+)\n', _cfg_text)
    # logger.debug(f'Got VDOM List: {_vdom_list}')
    return _vdom_list


def parse_set_line(_line, islist=False, current_path=[]):
    # Get set XXXX line and return it parsed to dict
    parsed_line = {}
    key_value_regex = re.compile(r'(?<=set )(\S+) (.+)')
    split_line = key_value_regex.findall(_line)[0]

    for _cfg_section, _params_where_list_is_possible in list_set_params.items():
        if _cfg_section in current_path and split_line[0] in _params_where_list_is_possible:
            islist = True

    if islist:
        parsed_line[split_line[0].replace('"', '')] = [item.replace('"', '') for item in re.findall(r'\"([^\"]+)\"', split_line[1])]
    else:
        parsed_line[split_line[0].replace('"', '')] = split_line[1].replace('"', '')
    return parsed_line


def parse_unset_line(_line):
    # Get unset XXXX line and return it parsed to dict
    parsed_line = {}
    key_value_regex = re.compile(r'(?<=unset )(.+)')
    split_line = key_value_regex.findall(_line)[0]
    parsed_line[split_line] = 'unset'
    return parsed_line


def extract_set_lines(_text, _indent):
    # Get all set lines with given indent
    regex = re.compile(r'(?:^|\n) {' + _indent + r'}(set (?:\S+) (?:\S+ ?)+)')
    # logger.debug(regex)
    return regex.findall(_text)


def extract_unset_lines(_text, _indent):
    # Get all set lines with given indent
    regex = re.compile(r'\n {' + _indent + r'}(unset (?:\S+) (?:\S+))')
    return regex.findall(_text)


def get_indent(level):
    return str(level * 4), str((level + 1) * 4)


def extract_config_section(_text, _indent, _next_indent):
    # Extract Config/Edit section. Return tuple (section_name, section_text)
    regex = \
        re.compile(r'(?:^|\n) {' +
                   _indent +
                   '}(?:config|edit) (?:\"?)([^\"|\n]+)(?:\"?)\n((?: {' +
                   _next_indent +
                   ',}.+\n)*)')
    # logger.debug(regex)
    return regex.findall(_text)


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def parse_section(cfg_chunk, _level, _path, parsed_cfg):
    indent, next_indent = get_indent(_level)
    _sections = extract_config_section(cfg_chunk, indent, next_indent)
    for _section in _sections:
        _next_path = _path + [_section[0]]
        _set_lines = extract_set_lines(_section[1], next_indent)
        _unset_lines = extract_unset_lines(_section[1], next_indent)
        set_unset_lines_dict = {}
        for _set_line in _set_lines:
            _parsed_line = parse_set_line(_set_line, current_path=_next_path)
            set_unset_lines_dict.update(_parsed_line)
        for _unset_line in _unset_lines:
            _parsed_line = parse_unset_line(_unset_line)
            set_unset_lines_dict.update(_parsed_line)
        nested_set(parsed_cfg, _next_path, set_unset_lines_dict)
        parse_section(_section[1], _level+1, _next_path, parsed_cfg)


def parse_vdom_config(_text):
    parsed_cfg = {}
    _current_chunk = _text
    level = 0
    path = []
    indent, next_indent = get_indent(level)
    parse_section(_text, level, path, parsed_cfg)

    return parsed_cfg


def pre_parse_config(_text):
    vdom_mode = int(re.findall(r':vdom=(\d):', _text)[0])
    # logger.debug(f'VDOM Mode: {vdom_mode}')
    if vdom_mode == 0:
        _vdom_list = ['global']
        # logger.debug('Single-VDOM Mode detected')
        _cfg_sections_dict = {
            'metadata_section': re.findall(r'((?:#.+\n){1,})', _text.lstrip().rstrip())[0],
            'global': re.findall(r'config system global[\w\W]+', _text)[0],
        }
    elif vdom_mode == 1:
        # logger.debug('Multi-VDOM Mode detected')
        _cfg_sections_list = _text.lstrip().rstrip().split('\n\n')
        _cfg_sections_dict = {
            'metadata_section': _cfg_sections_list[0],
            'vdom_list_section': _cfg_sections_list[1],
            'global': _cfg_sections_list[2]
        }
        _vdom_list = get_vdom_list(_cfg_sections_dict['vdom_list_section'])
        # logger.debug(f'VDOMs Found: {_vdom_list}')
        for _section in _cfg_sections_list[3:]:
            _parsed_section = re.findall(r'(?:config vdom\nedit )([^\n]+)\n([\w\W]+)(?:\nend)', _section)[0]
            _cfg_sections_dict.update({_parsed_section[0]: _parsed_section[1]})
    else:
        # logger.error('Unable to detect VDOM mode')
        pass
    return _cfg_sections_dict, _vdom_list


def parse_config(_cfg_text):
    _cfg_sections_dict, _vdom_list = pre_parse_config(_cfg_text)
    _parsed_config = {section: parse_vdom_config(text) for section, text in _cfg_sections_dict.items()}
    return _parsed_config, _vdom_list
