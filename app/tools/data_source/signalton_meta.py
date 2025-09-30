from threading import Lock


class SingletonMeta(type):
    _instances = {}
    _locks = {}

    def __new__(mcs, name, bases, dct):
        cls = super().__new__(mcs, name, bases, dct)
        if cls not in mcs._locks:
            mcs._locks[cls] = Lock()
        return cls

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._locks[cls]:
                if cls not in cls._instances:  # Double-checked locking
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]