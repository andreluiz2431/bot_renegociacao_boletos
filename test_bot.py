import unittest
from bot import calcular_multa_juros, calcular_parcelas

class TestCalcularMultaJuros(unittest.TestCase):
    def test_valor_zero(self):
        self.assertEqual(calcular_multa_juros(0, 10), 0)

    def test_dias_vencidos_zero(self):
        self.assertEqual(calcular_multa_juros(100, 0), 101)  # Apenas 1% de multa

    def test_valor_e_dias_vencidos_positivos(self):
        self.assertAlmostEqual(calcular_multa_juros(100, 10), 104.33, places=2)

    def test_valor_negativo(self):
        with self.assertRaises(ValueError):
            calcular_multa_juros(-100, 10)

    def test_dias_vencidos_negativo(self):
        with self.assertRaises(ValueError):
            calcular_multa_juros(100, -10)

class TestCalcularParcelas(unittest.TestCase):
    def test_total_divida_menor_que_100(self):
        self.assertEqual(calcular_parcelas(99), 0)

    def test_total_divida_igual_100(self):
        self.assertEqual(calcular_parcelas(100), 1)

    def test_total_divida_grande(self):
        self.assertEqual(calcular_parcelas(500), 5)

if __name__ == '__main__':
    unittest.main()
