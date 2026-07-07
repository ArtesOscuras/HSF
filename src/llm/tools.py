"""Agent tool definitions — OpenAI function calling schema + handlers."""

import os

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_user",
            "description": "Add a user to the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The username"},
                    "utype": {"type": "string", "enum": ["local", "domain"], "description": "User type"},
                    "machine": {"type": "string", "description": "Machine IP if local type"},
                    "domain": {"type": "string", "description": "Domain name if domain type"},
                    "origin": {"type": "string", "description": "How the user was found"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user",
            "description": "Delete a user from the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username to delete"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_machine",
            "description": "Add a machine (IP) to the network inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_domain",
            "description": "Add a domain to the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain name"},
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_credential",
            "description": "Add a credential (username + password or NT hash).",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username"},
                    "secret": {"type": "string", "description": "Password or 32-char NT hash"},
                },
                "required": ["username", "secret"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_hash",
            "description": "Add a hash entry to the hash inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hash_type": {"type": "string", "description": "Hash type name (e.g. NTLM, MD5)"},
                    "hash_value": {"type": "string", "description": "The hash string"},
                    "hascat_mode": {"type": "string", "description": "Optional hashcat mode"},
                },
                "required": ["hash_type", "hash_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_hash",
            "description": "Delete a hash from the inventory by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hash_id": {"type": "integer", "description": "Hash ID to delete"},
                },
                "required": ["hash_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_password",
            "description": "Add a password to the password inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "password": {"type": "string", "description": "The password string"},
                },
                "required": ["password"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_interfaces",
            "description": "List available network interfaces for scanning.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_interface",
            "description": "Scan the local network on a given interface, looking for machines. Use list_interfaces first to see available interfaces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "iface": {"type": "string", "description": "Interface name, e.g. en0"},
                },
                "required": ["iface"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_ip",
            "description": "Scan a specific IP address to identify the machine (device type, OS, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address to scan"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_scan",
            "description": "Stop the active network scan if one is running.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tcp_scan",
            "description": "Scan TCP ports on a specific IP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "udp_scan",
            "description": "Scan common UDP ports on a specific IP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ping",
            "description": "Ping an IP address to check if it's alive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address or hostname"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nslookup",
            "description": "DNS lookup — resolve a hostname to IP addresses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or domain to resolve"},
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatweb",
            "description": "Identify web technologies on an IP using WhatWeb.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IPv4 address"},
                    "port": {"type": "integer", "description": "Port number (default 80)"},
                },
                "required": ["ip"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_credential",
            "description": "Delete a credential by username.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username of the credential"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_machine",
            "description": "Delete a machine from the inventory by IP or ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Machine IP address or ID number"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_domain",
            "description": "Delete a domain from the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain name to delete"},
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_password",
            "description": "Delete a password from the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "password": {"type": "string", "description": "The password to delete"},
                },
                "required": ["password"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "webfetch",
            "description": "Fetch the content of a URL and return it as text or markdown. Use this to read a specific web page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch (http:// or https://)"},
                    "format": {"type": "string", "enum": ["text", "markdown"], "description": "Output format (default: markdown)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "websearch",
            "description": "Search the web and return results with title, URL, and snippet. Use this to find information about people, companies, or any topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "num_results": {"type": "integer", "description": "Number of results to return (default: 10)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_person",
            "description": "Add a person (real human, employee, contact) to the people inventory. Use for OSINT-discovered individuals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string", "description": "First name of the person"},
                    "last_name": {"type": "string", "description": "Last name(s) of the person"},
                    "company": {"type": "string", "description": "Company the person works for"},
                    "domain": {"type": "string", "description": "Domain associated with the person"},
                    "username": {"type": "string", "description": "OS username if linked to a system user"},
                    "role": {"type": "string", "description": "Job title or role"},
                    "linkedin_url": {"type": "string", "description": "LinkedIn profile URL"},
                    "source": {"type": "string", "description": "How this person was found (e.g. websearch, LinkedIn, agent)"},
                    "interests": {"type": "string", "description": "Known interests or topics"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_person",
            "description": "Delete a person from the people inventory by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "integer", "description": "Person ID to delete"},
                },
                "required": ["person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dicma_generate_users",
            "description": "Generate username permutations from a person's full name using DICMA. Saves the output to the wordlist directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Full name of the person, e.g. 'Joan Garcia'"},
                    "output_name": {"type": "string", "description": "Output filename (e.g. 'users.txt'). Default: dicma_users.txt"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dicma_find_related",
            "description": "Find semantically related words using the LLM via DICMA's neighbour expansion. Uses the active LLM config from HSF settings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "words": {"type": "string", "description": "Comma-separated seed words, e.g. 'football,music,hiking'"},
                    "n1": {"type": "integer", "description": "Number of level-1 neighbours per word (default: 50)"},
                    "n2": {"type": "integer", "description": "Optional level-2 neighbours per L1 result (default: 0)"},
                    "n3": {"type": "integer", "description": "Optional level-3 neighbours per L2 result (default: 0)"},
                    "output_name": {"type": "string", "description": "Output filename. Default: dicma_related.txt"},
                },
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dicma_generate_passwords",
            "description": "Generate password permutations from seed words using DICMA. Uses built-in suffix/prefix patterns. Saves to wordlist directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "words": {"type": "string", "description": "Comma-separated seed words, e.g. 'megacorp,summer2024'"},
                    "mode": {"type": "string", "enum": ["light", "normal", "full"], "description": "Generation mode (default: normal). Full mode creates massive output."},
                    "output_name": {"type": "string", "description": "Output filename. Default: dicma_passwords.txt"},
                },
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dicma_generate_rules",
            "description": "Generate hashcat rules from built-in patterns or a custom dictionary. Saves to the rules directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dictionary": {"type": "string", "description": "Optional dictionary filename from the wordlist directory to extract patterns from. Leave empty to use built-in rockyou-based patterns."},
                    "mode": {"type": "string", "enum": ["light", "normal", "full"], "description": "Generation mode (default: normal). Full mode creates massive output."},
                    "output_name": {"type": "string", "description": "Output filename. Default: dicma_rules.rule"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hashcat_crack",
            "description": "Crack a hash using hashcat with a wordlist. The hash must already be in the inventory (added via add_hash).",
            "parameters": {
                "type": "object",
                "properties": {
                    "hash_value": {"type": "string", "description": "The hash string to crack (must exist in inventory)"},
                    "wordlist": {"type": "string", "description": "Wordlist filename from the wordlist directory (e.g. 'rockyou.txt')"},
                },
                "required": ["hash_value", "wordlist"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bruteforce_start",
            "description": "Start a brute force attack against a target service. Uses credential and password inventories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "protocol": {"type": "string", "enum": ["ftp", "ssh", "smb", "rdp", "ldap", "mssql", "mysql", "pgsql"], "description": "Protocol to attack"},
                    "target": {"type": "string", "description": "Target IP address"},
                    "port": {"type": "integer", "description": "Port number (uses default if omitted)"},
                },
                "required": ["protocol", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fuzz_start",
            "description": "Start a directory, vhost or DNS subdomain fuzzing scan against a target. Blocks until scan completes and returns all found results. Directory mode fuzzes HTTP paths (e.g. /admin, /login), vhost mode fuzzes virtual host subdomains (Host header), dns mode fuzzes DNS subdomains. Results are NOT saved to database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["directory", "vhost", "dns"], "description": "Fuzzing method: 'directory' for URL paths, 'vhost' for virtual hosts, 'dns' for DNS subdomains"},
                    "target": {"type": "string", "description": "Target IP address, machine ID, or domain name"},
                    "wordlist": {"type": "string", "description": "Wordlist filename from the wordlist directory (e.g. 'common.txt', 'subdomains.txt')"},
                    "port": {"type": "integer", "description": "Port number (default: 80). Only used for 'directory' method."},
                },
                "required": ["method", "target", "wordlist"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_listener",
            "description": "Start a background service listener (shell listener or mDNS listener).",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "enum": ["shells-listener", "mdns-listener"], "description": "Service to start"},
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_listener",
            "description": "Stop a running background service listener.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "enum": ["shells-listener", "mdns-listener"], "description": "Service to stop"},
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dictionaries",
            "description": "List all dictionary wordlist files available in the wordlist directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_rules",
            "description": "List all hashcat rule files available in the rules directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a dictionary or rule file from the wordlist or rules directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_type": {"type": "string", "enum": ["dictionary", "rule"], "description": "Type of file to delete"},
                    "filename": {"type": "string", "description": "The filename to delete"},
                },
                "required": ["file_type", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_evidence",
            "description": "Delete an evidence session by name or all evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Evidence session name to delete, or 'all' to delete all evidence"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_shell",
            "description": "Delete a shell session by ID or all shell sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shell_id": {"type": "string", "description": "Shell session ID to delete, or 'all' to delete all"},
                },
                "required": ["shell_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_list",
            "description": "List all active shell sessions with their IDs, types, and statuses.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": (
                "Send a command to a shell session and wait briefly for initial output. "
                "The command may still be running when this returns. Check the result status: "
                "'finished' means a shell prompt was detected (command completed). "
                "'password' means a password prompt appeared (command auto-interrupted). "
                "'running' means the command is still producing output — use shell_wait to "
                "get more output, and shell_interrupt to stop it if it seems stuck."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shell_id": {"type": "integer", "description": "Shell session ID from shell_list"},
                    "command": {"type": "string", "description": "Command to execute (e.g. 'whoami', 'ls -la', 'find /')"},
                },
                "required": ["shell_id", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_wait",
            "description": (
                "Wait for more output from a running shell command. Call this after "
                "shell_exec returned status 'running' to get more output. Returns new output "
                "plus a status: 'finished' (prompt detected), 'running' (still producing), "
                "'paused' (no new output for 2s, might be waiting for input). "
                "Do NOT call this unless a command is actually running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shell_id": {"type": "integer", "description": "Shell session ID from shell_list"},
                },
                "required": ["shell_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_interrupt",
            "description": (
                "Interrupt the currently running command in a shell by sending Ctrl+C. "
                "Use this when a command seems stuck, is taking too long, shows a password "
                "prompt, or is an infinite command like 'ping' without a count limit. "
                "Returns any remaining output after the interrupt plus the new shell prompt."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shell_id": {"type": "integer", "description": "Shell session ID from shell_list"},
                },
                "required": ["shell_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_ssh",
            "description": (
                "Connect to a remote machine via SSH using stored credentials. "
                "Use this to open an interactive shell session. The host can be "
                "a machine ID (from inventory) or an IP address. The username "
                "must match an existing credential in the inventory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Machine ID or IP address"},
                    "username": {"type": "string", "description": "Username for authentication (must exist in credentials)"},
                    "port": {"type": "integer", "description": "SSH port (default 22)"},
                },
                "required": ["host", "username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_sftp",
            "description": (
                "Connect to a remote machine via SFTP using stored credentials. "
                "Use this for file transfer operations over SSH."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Machine ID or IP address"},
                    "username": {"type": "string", "description": "Username for authentication"},
                    "port": {"type": "integer", "description": "SFTP port (default 22)"},
                },
                "required": ["host", "username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_ftp",
            "description": (
                "Connect to a remote machine via FTP using stored credentials. "
                "Use this for file transfer operations over FTP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Machine ID or IP address"},
                    "username": {"type": "string", "description": "Username for authentication (use 'anonymous' for anonymous FTP)"},
                    "port": {"type": "integer", "description": "FTP port (default 21)"},
                },
                "required": ["host", "username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_winrm",
            "description": (
                "Connect to a remote Windows machine via WinRM using stored credentials. "
                "Use this to open an interactive PowerShell session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Machine ID or IP address"},
                    "username": {"type": "string", "description": "Username for authentication"},
                    "port": {"type": "integer", "description": "WinRM port (default 5985)"},
                },
                "required": ["host", "username"],
            },
        },
    },
]

_HANDLERS = {}


def register(name):
    def decorator(fn):
        _HANDLERS[name] = fn
        return fn
    return decorator


def execute(name, args_dict, tool_context=None):
    if tool_context and getattr(tool_context, "_agent_stop_event", None) and tool_context._agent_stop_event.is_set():
        return f"Tool '{name}' cancelled (agent stop requested)."
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return handler(args_dict, tool_context)
    except Exception as e:
        return f"Tool error: {e}"


# ─── Tool Handlers ──────────────────────────────────────────
# All handlers receive (args_dict, tool_context).
# tool_context is the App instance (or None).


@register("add_user")
def _add_user(args, ctx=None):
    from src.machines.credential_db import save_user
    save_user(
        username=args.get("username", ""),
        utype=args.get("utype", ""),
        machine=args.get("machine", ""),
        domain=args.get("domain", ""),
        origin=args.get("origin", "agent"),
    )
    return f"User '{args.get('username')}' added."


@register("delete_user")
def _delete_user(args, ctx=None):
    from src.machines.credential_db import delete_user, load_usernames
    username = args.get("username", "")
    if username not in load_usernames():
        return f"User '{username}' not found."
    delete_user(username)
    return f"User '{username}' deleted."


@register("add_machine")
def _add_machine(args, ctx=None):
    from src.machines import store, machine_db
    ip = args.get("ip", "")
    machine = store.add_or_update(ip=ip, method="agent")
    machine.device_type = "device unknown"
    machine_db.save_machine_info(machine)
    return f"Machine #{machine.id} ({ip}) added."


@register("add_domain")
def _add_domain(args, ctx=None):
    from src.machines import domain_db
    domain = args.get("domain", "")
    domain_db.init_or_update(domain, 0, "", "agent")
    return f"Domain '{domain}' added."


@register("add_credential")
def _add_credential(args, ctx=None):
    from src.machines.credential_db import save_credential, save_user
    username = args.get("username", "")
    secret = args.get("secret", "")
    import re
    nt_pattern = re.compile(r"^[a-fA-F0-9]{32}$")
    if nt_pattern.match(secret):
        cid = save_credential(username, "", hash_nt=secret, hash_nt_origin="agent")
        save_user(username, origin="agent")
        return f"Credential #{cid}: {username} (NT hash) added."
    from src.gui.views.user_pass import _ntlm_hash
    hnt = _ntlm_hash(secret)
    cid = save_credential(username, secret, hash_nt=hnt,
                          password_origin="agent", hash_nt_origin="agent")
    save_user(username, origin="agent")
    return f"Credential #{cid}: {username} / {secret} added."


@register("add_hash")
def _add_hash(args, ctx=None):
    from src.machines.credential_db import save_hash_entry
    hid = save_hash_entry(
        hash_type=args.get("hash_type", ""),
        hash_value=args.get("hash_value", ""),
        hascat_mode=args.get("hascat_mode", ""),
        origin="agent",
    )
    return f"Hash #{hid} added."


@register("delete_hash")
def _delete_hash(args, ctx=None):
    from src.machines.credential_db import delete_hash_entry
    hid = args.get("hash_id")
    delete_hash_entry(hid)
    return f"Hash #{hid} deleted."


@register("add_password")
def _add_password(args, ctx=None):
    from src.machines.credential_db import save_password
    save_password(args.get("password", ""))
    return "Password added."


@register("list_interfaces")
def _list_interfaces(args, ctx=None):
    from src.network_iface import interfaces, ifaddresses, AF_INET
    result = []
    for iface in interfaces():
        if iface == "lo0":
            continue
        addrs = ifaddresses(iface).get(AF_INET)
        if addrs:
            for a in addrs:
                result.append(f"  {iface}: {a['addr']}/{a['netmask']}")
    if not result:
        return "No network interfaces with IPv4 found."
    return "Available interfaces:\n" + "\n".join(result)


@register("scan_interface")
def _scan_interface(args, ctx=None):
    iface = args.get("iface", "")
    if not ctx:
        return "Cannot scan: no tool context available."
    ctx._scan_interface(iface)
    return (f"Network scan started on interface {iface}. "
            "Results will appear in inventory as machines are discovered.")


@register("scan_ip")
def _scan_ip(args, ctx=None):
    ip = args.get("ip", "")
    if not ctx:
        return "Cannot scan: no tool context available."
    ctx._scan_ip(ip)
    return f"IP scan started on {ip}. Results will appear in inventory."


@register("stop_scan")
def _stop_scan(args, ctx=None):
    if not ctx:
        return "Cannot stop: no tool context available."
    ctx._scan_stop()
    return "Active scan stopped."


@register("tcp_scan")
def _tcp_scan(args, ctx=None):
    ip = args.get("ip", "")
    if not ctx:
        return "Cannot scan: no tool context available."
    ctx._cmd_tcpscan([ip])
    return f"TCP scan started on {ip}. Results will appear in inventory."


@register("udp_scan")
def _udp_scan(args, ctx=None):
    ip = args.get("ip", "")
    if not ctx:
        return "Cannot scan: no tool context available."
    ctx._cmd_udpscan([ip])
    return f"UDP scan started on {ip}. Results will appear in inventory."


@register("ping")
def _ping(args, ctx=None):
    ip = args.get("ip", "")
    if not ctx:
        return "Cannot ping: no tool context available."
    ctx._cmd_ping([ip])
    return f"Ping sent to {ip}. Check console output."


@register("nslookup")
def _nslookup(args, ctx=None):
    host = args.get("host", "")
    if not ctx:
        return "Cannot lookup: no tool context available."
    ctx._cmd_nslookup([host])
    return f"DNS lookup started for {host}."


@register("banner_grab")
def _banner_grab(args, ctx=None):
    ip = args.get("ip", "")
    port = args.get("port", 80)
    if not ctx:
        return "Cannot grab banner: no tool context available."
    ctx._cmd_bannergrab([ip, str(port)])
    return f"Banner grab started on {ip}:{port}."


@register("whatweb")
def _whatweb(args, ctx=None):
    ip = args.get("ip", "")
    port = args.get("port", 80)
    if not ctx:
        return "Cannot scan: no tool context available."
    ctx._cmd_whatweb([ip])
    return f"WhatWeb scan started on {ip}:{port}."


@register("delete_credential")
def _delete_credential(args, ctx=None):
    from src.machines.credential_db import load_credentials, delete_credential
    username = args.get("username", "")
    for c in load_credentials():
        if c["username"] == username:
            delete_credential(c["id"])
            return f"Credential '{username}' deleted."
    return f"Credential '{username}' not found."


@register("delete_machine")
def _delete_machine(args, ctx=None):
    from src.machines import store, machine_db
    target = args.get("target", "")
    for m in store.get_all():
        if str(m.id) == target or m.ip == target:
            machine_db.delete_machine_db(m.id)
            store.remove(m.ip)
            return f"Machine #{m.id} ({m.ip}) deleted."
    return f"Machine '{target}' not found."


@register("delete_domain")
def _delete_domain(args, ctx=None):
    from src.machines import domain_db
    domain = args.get("domain", "")
    if domain_db.exists(domain):
        domain_db.delete_domain(domain)
        return f"Domain '{domain}' deleted."
    return f"Domain '{domain}' not found."


@register("delete_password")
def _delete_password(args, ctx=None):
    from src.machines.credential_db import delete_password, load_passwords
    pwd = args.get("password", "")
    if pwd in load_passwords():
        delete_password(pwd)
        return f"Password deleted."
    return f"Password not found."


@register("webfetch")
def _webfetch(args, ctx=None):
    from src.llm.web import fetch_url
    return fetch_url(
        args.get("url", ""),
        format=args.get("format", "markdown"),
    )


@register("websearch")
def _websearch(args, ctx=None):
    from src.llm.web import web_search
    return web_search(
        args.get("query", ""),
        num_results=args.get("num_results", 10),
    )


@register("add_person")
def _add_person(args, ctx=None):
    from src.machines.people_db import save_person
    pid = save_person(
        first_name=args.get("first_name", ""),
        last_name=args.get("last_name", ""),
        company=args.get("company", ""),
        domain=args.get("domain", ""),
        username=args.get("username", ""),
        role=args.get("role", ""),
        linkedin_url=args.get("linkedin_url", ""),
        source=args.get("source", "agent"),
        interests=args.get("interests", ""),
    )
    name = f"{args.get('first_name','')} {args.get('last_name','')}".strip() or f"#{pid}"
    return f"Person '{name}' added as #{pid}."


@register("delete_person")
def _delete_person(args, ctx=None):
    from src.machines.people_db import load_person, delete_person
    pid = args.get("person_id")
    if not pid:
        return "Missing person_id."
    p = load_person(int(pid))
    if not p:
        return f"Person #{pid} not found."
    delete_person(int(pid))
    name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
    return f"Person '{name}' (#{pid}) deleted."


@register("dicma_generate_users")
def _dicma_generate_users(args, ctx=None):
    from src.tools.dicma import engine as dicma
    from src.hsf_paths import lst_dir
    full_name = args.get("full_name", "")
    if not full_name:
        return "Missing full_name."
    out_name = args.get("output_name", "dicma_users.txt")
    out_path = os.path.join(str(lst_dir()), out_name)
    dicma.LIGHT_MODE = False
    dicma.OUTPUT_FILE_BULEAN = True
    dicma.VERBOSE = False
    dicma.process_input_user(full_name, out_path)
    return f"Usernames generated for '{full_name}' → saved to {out_path}"


@register("dicma_find_related")
def _dicma_find_related(args, ctx=None):
    from src.tools.dicma import engine as dicma
    from src.hsf_paths import lst_dir
    from src.llm.config import load as llm_load, get_provider, get_active_model
    words_str = args.get("words", "")
    if not words_str:
        return "Missing words."
    words = [w.strip() for w in words_str.split(",") if w.strip()]
    n1 = int(args.get("n1", 50))
    n2 = int(args.get("n2", 0))
    n3 = int(args.get("n3", 0))
    out_name = args.get("output_name", "dicma_related.txt")
    out_path = os.path.join(str(lst_dir()), out_name)
    config = llm_load()
    provider = get_provider(config)
    model = get_active_model(config)
    api_key = provider.get("api_key", "")
    base_url = provider.get("base_url", "")
    if not api_key or not base_url or not model:
        return "No active LLM config. Configure in Settings → Models."
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    expanded = dicma.ml_expand_words(client, model, words, n1, n2, n3)
    result = [w for w in expanded if w not in set(words)]
    dicma.save_list_to_file(result, out_path)
    return (f"Found {len(result)} related words from {len(words)} seed(s). "
            f"Saved to {out_path}")


@register("dicma_generate_passwords")
def _dicma_generate_passwords(args, ctx=None):
    from src.tools.dicma import engine as dicma
    from src.hsf_paths import lst_dir
    words_str = args.get("words", "")
    if not words_str:
        return "Missing words."
    words = [w.strip() for w in words_str.split(",") if w.strip()]
    mode = args.get("mode", "normal")
    out_name = args.get("output_name", "dicma_passwords.txt")
    out_path = os.path.join(str(lst_dir()), out_name)
    light = mode == "light"
    full = mode == "full"
    dicma.LIGHT_MODE = light
    dicma.FULL_MODE = full
    dicma.OUTPUT_FILE_BULEAN = True
    dicma.VERBOSE = False
    dicma._NO_MULTIPROC = True
    dicma.process_passwd(words, out_path)
    return f"Passwords generated ({mode} mode) from {len(words)} word(s) → saved to {out_path}"


@register("dicma_generate_rules")
def _dicma_generate_rules(args, ctx=None):
    from src.tools.dicma import engine as dicma
    from src.hsf_paths import lst_dir, rules_dir
    mode = args.get("mode", "normal")
    dict_name = args.get("dictionary", "")
    out_name = args.get("output_name", "dicma_rules.rule")
    out_path = os.path.join(str(rules_dir()), out_name)
    light = mode == "light"
    full = mode == "full"
    if dict_name:
        dict_path = os.path.join(str(lst_dir()), dict_name)
        if not os.path.isfile(dict_path):
            return f"Dictionary not found: {dict_name}"
        suffixes, prefixes, numbers, symbols = dicma.extract_patterns(dict_path)
        all_suf = list(dict.fromkeys(suffixes + numbers + symbols))
        all_pre = list(dict.fromkeys(prefixes + numbers + symbols))
    else:
        all_suf = list(dict.fromkeys(
            dicma.BASIC_SUFIXS + dicma.NUMERIC_PATTERNS + dicma.SYMBOLIC_PATTERNS))
        all_pre = list(dict.fromkeys(
            dicma.BASIC_PREFIXS + dicma.NUMERIC_PATTERNS + dicma.SYMBOLIC_PATTERNS))
    rules = dicma.generate_rules(all_suf, all_pre, light=light, full=full)
    dicma.save_list_to_file(rules, out_path)
    return f"{len(rules)} rules generated ({mode} mode) → saved to {out_path}"


@register("hashcat_crack")
def _hashcat_crack(args, ctx=None):
    if not ctx:
        return "Cannot crack: no tool context available."
    hash_val = args.get("hash_value", "")
    wordlist_name = args.get("wordlist", "")
    if not hash_val or not wordlist_name:
        return "Missing hash_value or wordlist."
    from src.machines.credential_db import load_hashes
    from src.hsf_paths import hashcat_db, lst_dir
    mode = None
    htype = ""
    for h in load_hashes():
        stored_hash = h.get("hash", "")
        if stored_hash == hash_val or (
                len(hash_val) >= 16 and stored_hash.startswith(hash_val)):
            htype = h.get("type", "")
            mode = h.get("hascat_mode", "")
            hash_val = stored_hash
            break
    if not mode and htype:
        try:
            import sqlite3
            conn = sqlite3.connect(str(hashcat_db()))
            row = conn.execute(
                'SELECT "Hash-Mode" FROM DefaultMode WHERE "Hash-Name" = ?',
                (htype,)).fetchone()
            conn.close()
            if row and row[0] and row[0] != -1:
                mode = str(row[0])
        except Exception:
            pass
    if not mode:
        return (f"Could not determine hashcat mode for '{hash_val[:30]}...'. "
                f"Add it via 'add_hash' first.")
    wl_path = os.path.join(str(lst_dir()), wordlist_name)
    if not os.path.isfile(wl_path):
        return f"Wordlist not found: {wordlist_name}"
    from src.tools.hashcat import HashcatEngine
    from src.machines.credential_db import save_password as _sp
    engine = HashcatEngine(
        mode=mode, hash_value=hash_val, wordlist=wl_path,
        on_output=lambda text, color=None: None,
        on_progress=lambda done, total, recovered: None,
        on_cracked=lambda hv, plain, sp=_sp: (
            ctx.console.after(0, lambda: ctx.console.success(
                f"Cracked: {plain}")),
            sp(plain)
        ),
        on_done=lambda cracked: ctx.console.after(0, lambda: ctx.console.info(
            f"Hashcat done. {len(cracked)} cracked.") if cracked
            else ctx.console.info("Hashcat done. No passwords found.")),
    )
    engine.start()
    return (f"Hashcat started: mode={mode} wordlist={wordlist_name} "
            f"hash='{hash_val[:30]}...'. Cracked passwords will be saved "
            f"to inventory automatically.")


@register("bruteforce_start")
def _bruteforce_start(args, ctx=None):
    if not ctx:
        return "Cannot start bruteforce: no tool context available."
    proto = args.get("protocol", "")
    target = args.get("target", "")
    port = args.get("port", 0)
    if not proto or not target:
        return "Missing protocol or target."
    ctx._cmd_use_bruteforce([proto, target, str(port)])
    return f"Bruteforce ({proto}) started against {target}."


@register("fuzz_start")
def _fuzz_start(args, ctx=None):
    if not ctx:
        return "Cannot start fuzzer: no tool context available."
    method = args.get("method", "")
    target = args.get("target", "")
    wordlist = args.get("wordlist", "")
    port = args.get("port", 80)
    if not method or not target or not wordlist:
        return "Missing method, target, or wordlist."
    from src.hsf_paths import lst_dir
    wl_path = os.path.join(str(lst_dir()), wordlist)
    if not os.path.isfile(wl_path):
        return f"Wordlist not found: {wordlist}"
    from src.tools.fuzz.results_db import clear_by_target, save_result
    clear_by_target(method, target)
    resolved_ip = None
    if method == "vhost":
        resolved_ip = ctx._resolve_to_ip(target)
    display_target = resolved_ip or target
    url_template = None
    if method == "directory":
        url_template = f"http://{display_target}:{port}/FUZZ"
    show_codes = {200, 201, 204, 301, 302, 307, 400, 401, 403, 405, 500, 502, 503}
    def _on_found(word, display):
        save_result(method, target, word, display)
    from src.tools.fuzz import FuzzEngine
    engine = FuzzEngine(
        target=target,
        wordlist_path=wl_path,
        method=method,
        target_ip=resolved_ip,
        url_template=url_template,
        workers=50,
        show_codes=show_codes,
        on_found=_on_found,
    )
    engine.start()
    return f"Fuzzing ({method}) started against {target} with {wordlist}. Results will be saved to the experimental fuzz results table (viewable via context)."


@register("start_listener")
def _start_listener(args, ctx=None):
    if not ctx:
        return "Cannot start listener: no tool context available."
    service = args.get("service", "")
    if service == "shells-listener":
        ctx._cmd_start(["shells-listener"])
    elif service == "mdns-listener":
        ctx._cmd_start(["mdns-listener"])
    else:
        return f"Unknown service: {service}"
    return f"{service} started."


@register("stop_listener")
def _stop_listener(args, ctx=None):
    if not ctx:
        return "Cannot stop listener: no tool context available."
    service = args.get("service", "")
    if service in ("shells-listener", "mdns-listener"):
        ctx._cmd_stop([service])
    else:
        return f"Unknown service: {service}"
    return f"{service} stopped."


@register("list_dictionaries")
def _list_dictionaries(args, ctx=None):
    from src.hsf_paths import lst_dir
    try:
        d = str(lst_dir())
        files = sorted(f for f in os.listdir(d)
                      if os.path.isfile(os.path.join(d, f)))
    except OSError:
        return "Could not read wordlist directory."
    if not files:
        return "No dictionary files found."
    result = f"Dictionary files in {d}:\n"
    for f in files:
        path = os.path.join(d, f)
        size = os.path.getsize(path)
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        result += f"  {f} ({size_str})\n"
    return result


@register("list_rules")
def _list_rules(args, ctx=None):
    from src.hsf_paths import rules_dir
    try:
        d = str(rules_dir())
        files = sorted(f for f in os.listdir(d)
                      if os.path.isfile(os.path.join(d, f)))
    except OSError:
        return "Could not read rules directory."
    if not files:
        return "No rule files found."
    result = f"Rule files in {d}:\n"
    for f in files:
        path = os.path.join(d, f)
        size = os.path.getsize(path)
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        result += f"  {f} ({size_str})\n"
    return result


@register("delete_file")
def _delete_file(args, ctx=None):
    from src.hsf_paths import lst_dir, rules_dir
    ftype = args.get("file_type", "")
    fname = args.get("filename", "")
    if not ftype or not fname:
        return "Missing file_type or filename."
    base = str(rules_dir()) if ftype == "rule" else str(lst_dir())
    path = os.path.join(base, fname)
    if not os.path.isfile(path):
        return f"File not found: {fname}"
    os.remove(path)
    return f"{ftype.capitalize()} '{fname}' deleted."


@register("delete_evidence")
def _delete_evidence(args, ctx=None):
    import shutil
    from src.hsf_paths import evidence_dir
    name = args.get("name", "")
    if not name:
        return "Missing evidence name."
    base = str(evidence_dir())
    if name == "all":
        if os.path.isdir(base):
            shutil.rmtree(base)
            os.makedirs(base, exist_ok=True)
        return "All evidence deleted."
    path = os.path.join(base, name)
    if not os.path.isdir(path):
        return f"Evidence session '{name}' not found."
    shutil.rmtree(path)
    return f"Evidence '{name}' deleted."


@register("delete_shell")
def _delete_shell(args, ctx=None):
    from src.shells import shell_db
    sid = args.get("shell_id", "")
    if not sid:
        return "Missing shell_id."
    if sid == "all":
        shells = shell_db.get_all()
        count = len(shells)
        for s in shells:
            shell_db.close_session(s["id"])
        return f"{count} shell session(s) deleted."
    try:
        shell_db.close_session(int(sid))
        return f"Shell session #{sid} deleted."
    except Exception:
        return f"Shell session #{sid} not found."


@register("shell_list")
def _shell_list(args, ctx=None):
    from src.shells import shell_db
    sessions = shell_db.get_all()
    if not sessions:
        return "No active shell sessions."
    result = []
    for s in sessions:
        stype = s.get("type", "?")
        status = s.get("status", "disconnected")
        ip = s.get("ip", "")
        result.append(f"  #{s['id']} {stype} {ip} ({status})")
    return "Shell sessions:\n" + "\n".join(result)


@register("shell_exec")
def _shell_exec(args, ctx=None):
    sid = int(args.get("shell_id", 0))
    cmd = args.get("command", "")
    if not sid or not cmd:
        return "Missing shell_id or command."
    from src.gui.views.shell_list import is_agent_allowed
    if not is_agent_allowed(sid):
        return (f"Agent access is disabled for shell #{sid}. "
                "Enable the 'Agent' toggle in that shell's view first.")
    from src.shells import shell_db, send_command, send_raw
    s = shell_db.get_session(sid)
    if not s:
        return f"Shell session #{sid} not found."
    if s.get("status") != "connected":
        return f"Shell #{sid} is not connected (status: {s.get('status', '?')})."
    shell_db.enable_agent_buffer(sid)
    shell_db.drain_agent_output(sid)
    shell_db.touch_agent(sid, cmd)
    if not send_command(sid, cmd):
        return f"Failed to send command to shell #{sid}."
    import time, re
    prefix = f"Shell #{sid} [{cmd[:80]}]: "
    all_out = []
    for _ in range(20):
        if ctx and getattr(ctx, "_agent_stop_event", None) and ctx._agent_stop_event.is_set():
            send_raw(sid, "\x03")
            time.sleep(0.3)
            out = shell_db.drain_agent_output(sid)
            if out:
                all_out.append(out)
            combined = "".join(all_out)
            return (f"{prefix}stopped by user\n{combined}"
                    if combined else f"{prefix}stopped by user before output arrived")
        time.sleep(0.1)
        out = shell_db.drain_agent_output(sid)
        if out:
            all_out.append(out)
    if not all_out:
        return f"{prefix}no immediate output [running] -- use shell_wait or shell_interrupt"
    combined = "".join(all_out)
    clean = re.sub(r'\x1b\][^\x07]*\x07', '', combined)
    clean = re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', clean)
    if re.search(r'(?i)(?:password|passphrase).*[:：]', clean):
        send_raw(sid, "\x03")
        time.sleep(0.5)
        out = shell_db.drain_agent_output(sid)
        if out:
            all_out.append(out)
        combined = "".join(all_out)
        return f"{prefix}password prompt detected, interrupted\n{combined}"
    if re.search(r'(?:^|\n)[^\n]*[$#>]\s*$', clean):
        return f"{prefix}[finished]\n{combined}"
    return f"{prefix}[running] -- use shell_wait for more output, shell_interrupt to stop\n{combined}"


@register("shell_wait")
def _shell_wait(args, ctx=None):
    sid = int(args.get("shell_id", 0))
    if not sid:
        return "Missing shell_id."
    from src.gui.views.shell_list import is_agent_allowed
    if not is_agent_allowed(sid):
        return (f"Agent access is disabled for shell #{sid}. "
                "Enable the 'Agent' toggle in that shell's view first.")
    from src.shells import shell_db, send_raw
    s = shell_db.get_session(sid)
    if not s:
        return f"Shell session #{sid} not found."
    if s.get("status") != "connected":
        return f"Shell #{sid} is not connected."
    import time, re
    prefix = f"Shell #{sid}: "
    all_out = []
    stale = 0
    for _ in range(100):
        if ctx and getattr(ctx, "_agent_stop_event", None) and ctx._agent_stop_event.is_set():
            send_raw(sid, "\x03")
            time.sleep(0.3)
            out = shell_db.drain_agent_output(sid)
            if out:
                all_out.append(out)
            combined = "".join(all_out)
            return (f"{prefix}stopped by user\n{combined}"
                    if combined else f"{prefix}stopped by user, no output")
        time.sleep(0.1)
        out = shell_db.drain_agent_output(sid)
        if out:
            all_out.append(out)
            stale = 0
        else:
            stale += 1
        if all_out:
            combined = "".join(all_out)
            clean = re.sub(r'\x1b\][^\x07]*\x07', '', combined)
            clean = re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', clean)
            if re.search(r'(?:^|\n)[^\n]*[$#>]\s*$', clean):
                return f"{prefix}[finished]\n{combined}"
        if stale > 20:
            if all_out:
                combined = "".join(all_out)
                return f"{prefix}[paused] -- output stopped, may be waiting for input or finished\n{combined}"
            else:
                return f"{prefix}[idle] -- no output, no command may be running"
    combined = "".join(all_out)
    return (f"{prefix}[running]\n{combined}"
            if combined else f"{prefix}[running] still no output after 10s")


@register("shell_interrupt")
def _shell_interrupt(args, ctx=None):
    sid = int(args.get("shell_id", 0))
    if not sid:
        return "Missing shell_id."
    from src.gui.views.shell_list import is_agent_allowed
    if not is_agent_allowed(sid):
        return (f"Agent access is disabled for shell #{sid}. "
                "Enable the 'Agent' toggle in that shell's view first.")
    from src.shells import shell_db, send_raw
    s = shell_db.get_session(sid)
    if not s:
        return f"Shell session #{sid} not found."
    if s.get("status") != "connected":
        return f"Shell #{sid} is not connected."
    import time, re
    prefix = f"Shell #{sid}: "
    send_raw(sid, "\x03")
    all_out = []
    for _ in range(20):
        time.sleep(0.1)
        if ctx and getattr(ctx, "_agent_stop_event", None) and ctx._agent_stop_event.is_set():
            out = shell_db.drain_agent_output(sid)
            if out:
                all_out.append(out)
            combined = "".join(all_out)
            return (f"{prefix}interrupted, also stopped by user\n{combined}"
                    if combined else f"{prefix}interrupted, also stopped by user")
        out = shell_db.drain_agent_output(sid)
        if out:
            all_out.append(out)
        combined = "".join(all_out)
        if combined:
            clean = re.sub(r'\x1b\][^\x07]*\x07', '', combined)
            clean = re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', clean)
            if re.search(r'(?:^|\n)[^\n]*[$#>]\s*$', clean):
                return f"{prefix}[interrupted]\n{combined}"
    combined = "".join(all_out)
    return (f"{prefix}[interrupted]\n{combined}"
            if combined else f"{prefix}[interrupted] no output after Ctrl+C")


def _resolve_target(ctx, target):
    import re
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
        return target
    if re.match(r"^\d+$", target):
        mid = int(target)
        from src.machines import store
        for m in store.get_all():
            if m.id == mid:
                return m.ip
    return None


def _find_credential(username):
    from src.machines import credential_db
    for c in credential_db.load_credentials():
        if c.get("username") == username:
            return c.get("password") or "", c.get("hash_nt") or ""
    return None, None


def _wait_connect(thread, timeout=15):
    import threading
    result = {}
    event = threading.Event()

    orig_on_connected = thread._on_connected
    orig_on_error = thread._on_error

    def on_connected(sid):
        result["ok"] = True
        result["sid"] = sid
        if orig_on_connected:
            orig_on_connected(sid)
        event.set()

    def on_error(msg):
        result["ok"] = False
        result["error"] = msg
        if orig_on_error:
            orig_on_error(msg)
        event.set()

    thread._on_connected = on_connected
    thread._on_error = on_error
    thread.start()
    if not event.wait(timeout=timeout):
        return f"Connection timed out after {timeout}s"
    if result.get("ok"):
        return f"Session #{result['sid']} connected successfully"
    return f"Connection failed: {result.get('error', 'unknown error')}"


@register("connect_ssh")
def _connect_ssh(args, ctx=None):
    if not ctx:
        return "Cannot connect: no tool context available."
    host = args.get("host", "")
    username = args.get("username", "")
    port = int(args.get("port", 22))
    if not host or not username:
        return "Missing host or username."
    ip = _resolve_target(ctx, host)
    if not ip:
        return f"Could not resolve target: {host}"
    password, _ = _find_credential(username)
    if password is None:
        return f"No credential found for username: {username}"
    from src.shells.ssh_shell import SSHConnectionThread
    t = SSHConnectionThread(ip, port, username, password)
    return f"SSH {ip}:{port} as {username}: {_wait_connect(t)}"


@register("connect_sftp")
def _connect_sftp(args, ctx=None):
    if not ctx:
        return "Cannot connect: no tool context available."
    host = args.get("host", "")
    username = args.get("username", "")
    port = int(args.get("port", 22))
    if not host or not username:
        return "Missing host or username."
    ip = _resolve_target(ctx, host)
    if not ip:
        return f"Could not resolve target: {host}"
    password, _ = _find_credential(username)
    if password is None:
        return f"No credential found for username: {username}"
    from src.shells.sftp_shell import SFTPConnectionThread
    t = SFTPConnectionThread(ip, port, username, password)
    return f"SFTP {ip}:{port} as {username}: {_wait_connect(t)}"


@register("connect_ftp")
def _connect_ftp(args, ctx=None):
    if not ctx:
        return "Cannot connect: no tool context available."
    host = args.get("host", "")
    username = args.get("username", "")
    port = int(args.get("port", 21))
    if not host or not username:
        return "Missing host or username."
    ip = _resolve_target(ctx, host)
    if not ip:
        return f"Could not resolve target: {host}"
    password = ""
    if username.lower() != "anonymous":
        password, _ = _find_credential(username)
        if password is None:
            return f"No credential found for username: {username}"
    from src.shells.ftp_shell import FTPConnectionThread
    t = FTPConnectionThread(ip, port, username, password)
    return f"FTP {ip}:{port} as {username}: {_wait_connect(t)}"


@register("connect_winrm")
def _connect_winrm(args, ctx=None):
    if not ctx:
        return "Cannot connect: no tool context available."
    host = args.get("host", "")
    username = args.get("username", "")
    port = int(args.get("port", 5985))
    if not host or not username:
        return "Missing host or username."
    ip = _resolve_target(ctx, host)
    if not ip:
        return f"Could not resolve target: {host}"
    _, hash_nt = _find_credential(username)
    if hash_nt is None:
        hash_nt = ""
    from src.shells.winrm_shell import WinRMConnectionThread
    t = WinRMConnectionThread(ip, port, username, "", hash_nt=hash_nt)
    return f"WinRM {ip}:{port} as {username}: {_wait_connect(t, timeout=15)}"
