import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Settings, load_csv


class SurveyValidationTests(unittest.TestCase):
    def read(self, row):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'survey.csv'
            path.write_text('ax,bx,mx,nx,rhoa,error\n' + row, encoding='utf-8')
            return load_csv(path)

    def test_valid_wenner(self):
        self.assertEqual(self.read('0,3,1,2,100,0.03')[0]['rhoa'], 100)

    def test_invalid_scientific_inputs(self):
        for row in ['0,3,1,2,nan,0.03', '0,3,1,2,-1,0.03',
                    '0,3,1,2,100,3', '0,3,0,2,100,0.03',
                    '-1,1,0,2,100,0', '0,3,1,2,100,inf', '']:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.read(row)

    def test_bad_settings(self):
        for settings in [Settings(preset='unknown'), Settings(regularization=float('nan')),
                         Settings(max_iterations=0), Settings(start_resistivity=-1)]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                settings.validate()


if __name__ == '__main__':
    unittest.main()
