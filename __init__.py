import json
from .core import Drift
from .services import Services
from .packages import Packages

TOOLS = {
    'drift_baseline': ('Record a user-selected list of local files as SHA-256 hashes, sizes and permissions. File contents are not stored.', {'paths': {'type': 'array', 'minItems': 1, 'maxItems': 1000, 'items': {'type': 'string'}}, 'follow_symlinks': {'type': 'boolean', 'description': 'Measure the file a listed symlink points to and record where it points; a changed target is reported as drift. Default false.'}}, ['paths']),
    'drift_baseline_packages': ('Record installed versions of explicitly selected Debian packages without changing them.', {'packages': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'items': {'type': 'string'}}}, ['packages']),
    'drift_compare_packages': ('Compare selected Debian package versions against a saved baseline.', {'baseline_id': {'type': 'string'}}, ['baseline_id']),
    'drift_baseline_services': ('Record read-only state of explicitly selected systemd services.', {'units': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'items': {'type': 'string'}}, 'scope': {'type': 'string', 'enum': ['user', 'system']}}, ['units']),
    'drift_compare_services': ('Compare selected service states against a saved baseline without changing services.', {'baseline_id': {'type': 'string'}}, ['baseline_id']),
    'drift_compare': ('Compare current files against the selected baseline and report changed, missing or inaccessible files.', {'baseline_id': {'type': 'string'}}, ['baseline_id']),
    'drift_list_baselines': ('List saved file, service and package baseline IDs without displaying their contents.', {}, []),
}

def invoke(name, args):
    from plugins.plugin_storage import plugin_data_dir
    try:
        root = plugin_data_dir('environment-drift-watch')
        if name in ('drift_baseline_packages', 'drift_compare_packages'):
            return json.dumps(getattr(Packages(root), name.removeprefix('drift_'))(**args))
        if name in ('drift_baseline_services', 'drift_compare_services'):
            return json.dumps(getattr(Services(root), name.removeprefix('drift_'))(**args))
        return json.dumps(getattr(Drift(root), name.removeprefix('drift_'))(**args))
    except (ValueError, TypeError, OSError, KeyError, RuntimeError) as exc:
        return json.dumps({'error': str(exc)})

def register(ctx):
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='environment_drift_watch', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args))
