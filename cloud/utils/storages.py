class Storage:
    all = []

    def __init__(self, name, priority, capacity=50):
        self.name = name
        self.priority = priority
        self.capacity = capacity  # in GB
        Storage.all.append(self)


class GoogleDriveStorage(Storage):
    def __init__(self, name="Google Drive", priority=1, capacity=60):
        super().__init__(name, priority, capacity)


class AppwriteStorage(Storage):
    def __init__(self, name="Appwrite", priority=2, capacity=50):
        super().__init__(name, priority, capacity)


class LocalStorage(Storage):
    def __init__(self, name="Local", priority=3, capacity=50):
        super().__init__(name, priority, capacity)
