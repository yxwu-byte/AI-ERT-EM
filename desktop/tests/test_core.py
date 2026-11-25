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

    def test_parameter_ranges_and_bounds(self):
        for settings in [Settings(vertical_weight=0), Settings(vertical_weight=2),
                         Settings(lambda_factor=float('nan')), Settings(error_floor=1),
                         Settings(min_phi_change=-1), Settings(mesh_depth=0),
                         Settings(max_cell_area=float('inf')), Settings(lower_resistivity=1),
                         Settings(lower_resistivity=100, upper_resistivity=200),
                         Settings(lower_resistivity=1, upper_resistivity=50),
                         Settings(robust_data='true')]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                settings.validate()

    def test_old_saved_settings_keep_defaults(self):
        settings = Settings(**dict(preset='Smooth model', regularization=20,
                                  max_iterations=10, start_resistivity=100))
        settings.validate()
        self.assertIsNone(settings.mesh_depth)
        self.assertFalse(settings.robust_data)
        self.assertNotIn('limits', settings.inversion_options())


if __name__ == '__main__':
    unittest.main()
