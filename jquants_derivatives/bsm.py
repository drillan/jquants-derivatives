import numpy as np
from scipy.optimize import fsolve
from scipy.stats import norm


def _d1(s: float, k: float, t: float, r: float, sigma: float) -> float:
    return ((np.log(s / k)) + (r + sigma**2 * 0.5 * t)) / (sigma * np.sqrt(t))


def _d2(d1: float, sigma: float, t: float) -> float:
    return d1 - sigma * np.sqrt(t)


def vega(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    return s * norm.pdf(d1) * np.sqrt(t)


def delta_call(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    return norm.cdf(d1)


def delta_put(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    return norm.cdf(d1) - 1


def delta(s: float, k: float, t: float, r: float, sigma: float, div: int) -> float:
    return {1: delta_put, 2: delta_call}[div](s, k, t, r, sigma)


def gamma(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    return norm.pdf(d1) / (s * sigma * np.sqrt(t))


def theta_call(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    d2 = _d2(d1, sigma, t)
    return (-s * norm.pdf(d1) * sigma / (2 * np.sqrt(t))) - (
        r * k * np.exp(-r * t) * norm.cdf(d2)
    )


def theta_put(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    d2 = _d2(d1, sigma, t)
    return (-s * norm.pdf(d1) * sigma / (2 * np.sqrt(t))) + (
        r * k * np.exp(-r * t) * norm.cdf(-d2)
    )


def theta(s: float, k: float, t: float, r: float, sigma: float, div: int) -> float:
    return {1: theta_put, 2: theta_call}[div](s, k, t, r, sigma)


def price_call(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    d2 = _d2(d1, sigma, t)
    return s * norm.cdf(d1) - k * np.exp(-r * t) * norm.cdf(d2)


def price_put(s: float, k: float, t: float, r: float, sigma: float) -> float:
    d1 = _d1(s, k, t, r, sigma)
    d2 = _d2(d1, sigma, t)
    return k * np.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1)


def implied_volatility(
    s: float, k: float, t: float, r: float, price: float, div: int
) -> float:
    def find_volatility(sigma):
        return {1: price_put, 2: price_call}[div](s, k, t, r, sigma) - price

    sigma0 = np.sqrt(abs(np.log(s / k) + r * t) * 2 / t)
    return fsolve(find_volatility, sigma0)[0]


def implied_volatility_call(
    s: float, k: float, t: float, r: float, price: float
) -> float:
    return implied_volatility(s, k, t, r, price, 2)


def implied_volatility_put(
    s: float, k: float, t: float, r: float, price: float
) -> float:
    return implied_volatility(s, k, t, r, price, 1)
