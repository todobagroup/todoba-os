class MemoryEngine:
    def __init__(self):
        self._objects = {}

    def save(self, obj):
        object_id = getattr(obj, "task_id", None)

        if object_id is None:
            object_id = getattr(obj, "experience_id", None)

        if object_id is None:
            raise ValueError("Object has no unique id.")

        self._objects[object_id] = obj
        return obj

    def get(self, object_id):
        return self._objects.get(object_id)

    def list(self):
        return list(self._objects.values())

    def delete(self, object_id):
        self._objects.pop(object_id, None)


memory_engine = MemoryEngine()