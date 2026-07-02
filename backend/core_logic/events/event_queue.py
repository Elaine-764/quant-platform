from collections import deque

class EventQueue:
    def __init__(self):
        self.queue = deque()

    def put(self, event):
        self.queue.append(event)

    def get(self):
        return self.queue.popleft()

    def is_empty(self):
        return len(self.queue) == 0