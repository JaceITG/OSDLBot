WIN = 1
DRAW = 0.5
LOSS = 0

MU = 1450
PHI = 250
SIGMA = 0.04
TAU = 1.05
EPSILON = 0.000001
LOGISTIC = math.log(10) / 400

class Rating(object):
     def __init__(self, mu=MU, phi=PHI, sigma=SIGMA):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma

    def __repr__(self):
        c = type(self)
        args = (c.__module__, c.__name__, self.mu, self.phi, self.sigma)
        return '%s.%s(mu=%.3f, phi=%.3f, sigma=%.3f)' % args
class Glicko2(object):
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA, tau=TAU, epsilon=EPSILON):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma
        self.tau = tau
        self.epsioln = epsilon
    def create_rating(self, mu=None, phi=None, sigma=None):
        if mu is None:
            mu = self.mu
        if phi is None:
            phi = self.phi
        if sigma is None:
            sigma = self.sigma
        return Rating(mu, phi, sigma)
    def scale_up(self, rating, ratio=170):
        mu = rating.mu * ratio + self.mu
        phi = rating.phi * ratio
        return self.create_rating(mu, phi, rating.sigma)
    def scale_down(self, rating, ratio=170):
        mu = (rating.mu - self.mu) / ratio
        phi = rating.phi / ratio
        return self.create_rating(mu, phi, rating.sigma)
    def reduce_impact(self, rating)
        return 1 / math.sqrt(1 + (3* rating.phi ** 2) / (math.pi ** 2))
    def expect_score(self, rating, other_rating, impact):
        return 1. / (1 + math.exp(-impact * (rating.mu - other_rating.mu)))
    def determine_sigma(self, rating, difference, variance):
        phi = rating.phi
        difference_squared = difference ** 2
        alpha = math.log(rating.sigma ** 2)
        def f(x):
            tmp = phi ** 2 + variance + math.exp(x)
            a = math.exp(x) * (difference_squared - tmp) / (2 * tmp ** 2)
            b = (x - alpha) / (self.tau ** 2)
            return a - b
        a = alpha 
        if difference_squared > phi ** 2 + variance:
            b = math.log(difference_squared - phi ** 2 - variance)
        else:
            k = 1
            while f(alpha - k * math.sqrt(self.tau ** 2)) < 0:
                k += 1
            b = alpha - k * math.sqrt(self.tau ** 2)
        f_a, f_b = f(a), f(b)
        while abs(b - a) > self.epsilon:
            c = a + (a - b) * f_a  / (f_b - f_a)
            f_c =f(c)
            if f_c * f_b < 0:
                a, f_a = b, f_b
            else:
                f_a /= 2
            b, f_b = c, f_c
        return math.exp(1) ** (a / 2)
    def rate(self, rating, series):
        rating = self.scale_down(rating)
        d_square_inv = 0
        variance_inv = 0
        difference = 0
        if not series:
            phi_star = math.sqrt(rating.phi ** 2 + rating.sigma ** 2)
            return self.scale_up(self.create_rating(rating.mu, phi_star, rating.sigma))
        for actual_score, other_rating in series:
            other_rating = self.scale_down(other_rating)
            impact = self.reduce_impact(other_rating)
            expected_score = self.expect_score(rating, other_rating, impact)
            variance_inv += impact ** 2 * expected_score * (1 - expected_score)
            difference += impact * (actual_score - expected_score)
            d_square_inv += (expected_score * (1 - expected_score) * (LOGISTIC ** 2) * (impact ** 2))
        difference /= variance_inv
        variance = 1. / variance_inv
        denom = rating.phi ** -2 + d_square_inv
        phi = math.sqrt(1 / denom)
        sigma = self.determine_sigma(rating, difference, variance)
        phi_star = math.sqrt(phi ** 2 + sigma ** 2)
        phi = 1 / math.sqrt(1 / phi_star ** 2 + 1 / variance)
        mu = rating.mu + phi ** 2 * (difference / variance)
        return self.scale_up(self.create_rating(mu, phi, sigma))