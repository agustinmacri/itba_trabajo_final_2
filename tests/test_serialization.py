import json
import unittest
from datetime import date, datetime
from decimal import Decimal

from src.serialization import to_json


class TestSerialization(unittest.TestCase):
    def test_dates_become_iso_text(self):
        data = json.loads(to_json({"d": datetime(2018, 3, 21, 10, 5), "day": date(2018, 3, 21)}))

        self.assertEqual(data["d"], "2018-03-21T10:05:00")
        self.assertEqual(data["day"], "2018-03-21")

    def test_decimal_becomes_number(self):
        data = json.loads(to_json({"price": Decimal("28.90")}))

        self.assertEqual(data["price"], 28.9)

    def test_none_becomes_null(self):
        self.assertEqual(to_json({"carrier_date": None}), '{"carrier_date": null}')

    def test_portuguese_text_stays_readable(self):
        self.assertIn("não chegou", to_json({"message": "não chegou"}))

    def test_unknown_type_fails_loudly(self):
        with self.assertRaises(TypeError):
            to_json({"x": object()})


if __name__ == "__main__":
    unittest.main()
