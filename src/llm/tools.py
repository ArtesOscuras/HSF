"""Agent tool definitions — OpenAI function calling schema + handlers."""

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
            "name": "banner_grab",
            "description": "Grab the service banner from a port on an IP.",
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
]

_HANDLERS = {}


def register(name):
    def decorator(fn):
        _HANDLERS[name] = fn
        return fn
    return decorator


def execute(name, args_dict, tool_context=None):
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
    ctx._cmd_bannergrab([ip])
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
