#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math, glob
from xml.etree import ElementTree
from scipy.optimize import brentq


class Calibration:

    def __init__(self, f_per_half_height, a=None, b=None, c=None, k1=None, type_="rectilinear", aspect_ratio=1.5):
        self.f_per_half_height, self.a, self.b, self.c, self.k1, self.type_, self.aspect_ratio = \
                f_per_half_height, a, b, c, k1, type_, aspect_ratio

    def de_ptlens(self, r_):
        upper_limit = 2
        while True:
            try:
                return brentq(lambda r: r * (self.a * r**3 + self.b * r**2 + self.c * r + 1 - self.a - self.b - self.c) - r_,
                              0, upper_limit)
            except ValueError:
                upper_limit += 1
                if upper_limit > 10:
                    return float("inf")

    def de_poly3(self, r_):
        upper_limit = 2
        while True:
            try:
                return brentq(lambda r: r * (self.k1 * r**2 + 1 - self.k1) - r_, 0, upper_limit)
            except ValueError:
                upper_limit += 1
                if upper_limit > 10:
                    return float("inf")

    def de_fisheye(self, r):
        return self.f_per_half_height * math.tan(r / self.f_per_half_height)

    def de_equisolidangle(self, r):
        return self.f_per_half_height * math.tan(2 * math.asin(r / self.f_per_half_height / 2))

    def de_stereographic(self, r):
        return self.f_per_half_height * math.tan(2 * math.atan(r / self.f_per_half_height / 2))

    def get_scaling(self, x, y):
        r_ = math.hypot(x, y)
        r = self.de_poly3(r_) if self.a is None else self.de_ptlens(r_)
        if self.type_ == "rectilinear":
            pass
        elif self.type_ == "fisheye":
            r = self.de_fisheye(r)
        elif self.type_ == "equisolidangle":
            r = self.de_equisolidangle(r)
        elif self.type_ == "stereographic":
            r = self.de_stereographic(r)
        return r_ / r

    def get_autoscale(self, samples):
        scalings = []
        for i in range(samples):
            x = self.aspect_ratio * (-1 + i / samples * 2)
            scalings.append(self.get_scaling(x, -1))
            scalings.append(self.get_scaling(x, +1))
        samples = int(math.ceil(samples / self.aspect_ratio / 2)) * 2
        for i in range(samples):
            y = -1 + i / samples * 2
            scalings.append(self.get_scaling(- self.aspect_ratio, y))
            scalings.append(self.get_scaling(+ self.aspect_ratio, y))
        return max(scalings) or 1

    def get_perfect_sample_number(self):
        perfect_autoscale = self.get_autoscale(100)
        samples = 1
        scalings = []
        while True:
            scalings.append(self.get_autoscale(samples))
            if all(abs(scaling - perfect_autoscale) / perfect_autoscale < 1e-3 for scaling in scalings[-3:]):
                return samples
            samples += 1


perfect_sample_numbers = set()
for filename in glob.glob("/home/bronger/src/lensfun/data/db/*.xml"):
    tree = ElementTree.parse(filename)
    for lens in tree.findall("lens"):
        type_element = lens.find("type")
        type_ = "rectilinear" if type_element is None else type_element.text.strip()
        crop_factor = float(lens.find("cropfactor").text)
        aspect_ratio_element = lens.find("aspect-ratio")
        if aspect_ratio_element is None:
            aspect_ratio = 1.5
        else:
            numerator, __, denominator = aspect_ratio_element.text.partition(":")
            if denominator:
                aspect_ratio = float(numerator) / float(denominator)
            else:
                aspect_ratio = float(numerator)
        calibration_element = lens.find("calibration")
        if calibration_element is not None:
            for distortion in calibration_element.findall("distortion"):
                f_per_half_height = float(distortion.attrib.get("focal")) / (12 / crop_factor)
                model = distortion.attrib.get("model")
                if model == "ptlens":
                    calibration = Calibration(f_per_half_height,
                                              a=float(distortion.attrib.get("a", 0)),
                                              b=float(distortion.attrib.get("b", 0)),
                                              c=float(distortion.attrib.get("c", 0)), type_=type_, aspect_ratio=aspect_ratio)
                elif model == "poly3":
                    calibration = Calibration(f_per_half_height, k1=float(distortion.attrib.get("k1", 0)),
                                              type_=type_, aspect_ratio=aspect_ratio)
                else:
                    continue
                perfect_sample_number = calibration.get_perfect_sample_number()
                perfect_sample_numbers.add(perfect_sample_number)
                print(lens.find("model").text, distortion.attrib.get("focal"), perfect_sample_number)
print(perfect_sample_numbers)
