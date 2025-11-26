import numpy as np

class ExponentialSmoother:
    """
    Smooths noisy hand-tracking coordinates.
    Internal mechanics:
    - Keeps last value
    - new = alpha * new + (1 - alpha) * old
    """

    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.prev_x = None
        self.prev_y = None

    def smooth(self, x, y):
        if self.prev_x is None:
            self.prev_x, self.prev_y = x, y
            return x, y

        sx = self.alpha * x + (1 - self.alpha) * self.prev_x
        sy = self.alpha * y + (1 - self.alpha) * self.prev_y

        self.prev_x, self.prev_y = sx, sy
        return int(sx), int(sy)


class KalmanPointTracker:
    """
    Simple Kalman filter for stable pointer movements.
    State: [x, y, dx, dy]
    """

    def __init__(self):
        dt = 1.0

        # State transition matrix
        self.A = np.array([[1, 0, dt, 0],
                           [0, 1, 0, dt],
                           [0, 0, 1,  0],
                           [0, 0, 0,  1]])

        # Observation matrix
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]])

        self.P = np.eye(4) * 1000  # initial uncertainty
        self.Q = np.eye(4) * 0.01  # movement noise
        self.R = np.eye(2) * 5     # measurement noise

        self.x = np.zeros((4,1))   # state vector

        self.initialized = False

    def update(self, meas_x, meas_y):
        z = np.array([[meas_x], [meas_y]])

        if not self.initialized:
            self.x[0, 0] = meas_x
            self.x[1, 0] = meas_y
            self.initialized = True
            return meas_x, meas_y

        # Prediction Step
        self.x = self.A @ self.x
        self.P = self.A @ self.P @ self.A.T + self.Q

        # Measurement Update
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        y = z - (self.H @ self.x)
        self.x = self.x + (K @ y)
        self.P = (np.eye(4) - K @ self.H) @ self.P

        return int(self.x[0, 0]), int(self.x[1, 0])
