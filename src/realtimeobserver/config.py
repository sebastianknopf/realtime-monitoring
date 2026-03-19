import yaml
import copy


class _ConfigNamespace:
    def __init__(self, **entries):
        for key, value in entries.items():
            setattr(self, key, value)

    def dict(self):
        return self.__dict__
    
    def __repr__(self):
        return f"<Config {self.__dict__}>"


class Configuration:

    REQUIRED: list[tuple[str]] = [
        ('app', 'adapter', 'type'),
        ('app', 'adapter', 'endpoint'),
        ('app', 'gtfs')
    ]

    DEFAULT: dict[str, any] = {
        'app': {
            'adapter': {
                'token': None
            },
            'lines': []
        }
    }
    
    @classmethod
    def apply_config(cls, config_filename: dict) -> None:
        
        cls._original_filename: str = config_filename
        
        with open(config_filename, 'r') as config_file:
            config: dict = yaml.safe_load(config_file)

        cls._apply_config_internal(config)

    @classmethod
    def apply_dict(cls, data: dict) -> None:
        cls._apply_config_internal(data)

    @classmethod
    def dump_config(cls, filename: str|None = None) -> None:
        data: dict = cls._dump_config_internal()        

        if filename is None and cls._original_filename is None:
            raise ValueError("Filename parameter must not be None because configuration was not loaded from a file initially.")
        
        if filename is None:
            filename = cls._original_filename
            
        with open(filename, 'w', encoding='utf-8') as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)

    @classmethod
    def dump_dict(cls) -> str:
        data: dict = cls._dump_config_internal()
        return data

    @classmethod
    def _apply_config_internal(cls, config: dict) -> None:

        # keep a copy of the original (as read) so we can preserve ordering
        cls._original_config = copy.deepcopy(config)

        cls._validate_required(cls.REQUIRED, config)
        config = cls._merge_config(cls.DEFAULT, config)

        namespace = cls._dict_to_namespace(config)
        for key, value in namespace.__dict__.items():
            setattr(cls, key, value)

        # remember which keys were applied (preserve insertion order)
        cls._config_keys = list(namespace.__dict__.keys())
    
    @classmethod
    def _dump_config_internal(cls) -> dict:
        keys = getattr(cls, '_config_keys', None)

        if keys is None:
            keys = [
                k for k, v in cls.__dict__.items()
                if not k.startswith('_') and not callable(v)
            ]

        original = getattr(cls, '_original_config', None) or {}
        defaults = getattr(cls, 'DEFAULT', None) or {}

        data = {}
        for k in keys:
            applied = getattr(cls, k)
            orig_sub = original.get(k) if isinstance(original, dict) else None
            def_sub = defaults.get(k) if isinstance(defaults, dict) else None
            data[k] = cls._reconstruct_value(applied, orig_sub, def_sub)

        return data
    
    @classmethod
    def _merge_config(cls, defaults, actual):
        if isinstance(actual, list) and isinstance(defaults, dict):
            return [
                cls._merge_config(defaults, item)
                for item in actual
            ]

        if isinstance(defaults, dict) and isinstance(actual, dict):
            # preserve key order: keys from defaults first, then any extra keys from actual
            keys = list(defaults.keys()) + [k for k in actual.keys() if k not in defaults]
            return {
                k: cls._merge_config(
                    defaults.get(k),
                    actual.get(k)
                )
                for k in keys
            }

        return actual if actual is not None else defaults
    
    @classmethod
    def _validate_required(cls, required: list[tuple[str]], config: dict):
        for path in required:
            cls._validate_path(config, path)

    @classmethod
    def _validate_path(cls, current, path: tuple[str]):
        if not path:
            return

        if isinstance(current, list):
            for idx, item in enumerate(current):
                cls._validate_path(item, path)
            return

        key = path[0]

        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"Missing required config key: {'.'.join(path)}")

        cls._validate_path(current[key], path[1:])

    @classmethod
    def _dict_to_namespace(cls, data):
        if isinstance(data, dict):
            return _ConfigNamespace(
                **{k: cls._dict_to_namespace(v) for k, v in data.items()}
            )

        if isinstance(data, list):
            return [cls._dict_to_namespace(v) for v in data]

        return data

    @classmethod
    def _namespace_to_dict(cls, value):
        if isinstance(value, _ConfigNamespace):
            return {k: cls._namespace_to_dict(v) for k, v in value.__dict__.items()}

        if isinstance(value, list):
            return [cls._namespace_to_dict(v) for v in value]

        return value

    @classmethod
    def _reconstruct_value(cls, applied, original, defaults):
        # lists: reconstruct per-element using original list items when available
        if isinstance(applied, list):
            result = []
            for idx, item in enumerate(applied):
                orig_item = None
                def_item = None
                if isinstance(original, list) and idx < len(original):
                    orig_item = original[idx]
                if isinstance(defaults, list) and idx < len(defaults):
                    def_item = defaults[idx]

                # if defaults is a dict (common pattern), pass it as defaults
                if isinstance(defaults, dict):
                    def_item = defaults
                result.append(cls._reconstruct_value(item, orig_item, def_item))
            return result

        # namespaces/dicts
        if isinstance(applied, _ConfigNamespace):
            applied_dict = applied.__dict__
        elif isinstance(applied, dict):
            applied_dict = applied
        else:

            # primitive
            return applied

        original_keys = list(original.keys()) if isinstance(original, dict) else []
        default_keys = list(defaults.keys()) if isinstance(defaults, dict) else []

        # keys: original order first, then defaults not in original, then any extras
        ordered_keys = []
        ordered_keys.extend(original_keys)
        ordered_keys.extend([k for k in default_keys if k not in ordered_keys])
        ordered_keys.extend([k for k in applied_dict.keys() if k not in ordered_keys])

        out = {}
        for key in ordered_keys:
            val = applied_dict.get(key)
            orig_sub = original.get(key) if isinstance(original, dict) else None
            def_sub = defaults.get(key) if isinstance(defaults, dict) else None
            out[key] = cls._reconstruct_value(val, orig_sub, def_sub)

        return out