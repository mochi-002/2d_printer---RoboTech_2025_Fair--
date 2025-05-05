import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import os


class PencilPlotterGenerator:
    def __init__(self):
        self.params = {
            # Plotter Settings
            'origin': 'lower_left',  # lower_left or center
            'x_offset': 5.0,  # mm
            'y_offset': 5.0,  # mm
            'return_to_zero': True,

            # Pencil Control
            'draw_speed': 150,  # mm/min
            'travel_speed': 800,  # mm/min
            'z_initial_position': 3.0,  # mm (3 = pen end)
            'z_drawing_position': 0.0,  # mm (0 = pen down)
            'z_lift_position': 1.0,  # mm (1 = pen up)
            'z_clearance': 1.0,  # mm
            'z_speed': 200,  # mm/min
            'z_change_delay': 1.5,  # seconds

            # Image Processing
            'image_size': (30, 25),  # mm
            'dpi': 1200,
            'contrast': 1.8,
            'min_feature_size': 0.1,  # mm (more details)
            'simplify_tolerance': 0.05  # mm (tighter tolerance)
        }

    def process_image_to_gcode(self):
        """Complete processing pipeline"""
        try:
            image_path, output_file = self._get_user_inputs()
            img = self._load_and_enhance_image(image_path)
            binary = self._create_clean_mask(img)

            contours = self._find_contours(binary)
            if not contours:
                print("Error: No contours found in image")
                return

            scaled_contours = self._scale_and_sort_contours(contours)
            self._write_plotter_gcode(scaled_contours, output_file)
            print(f"Success! G-code saved to {output_file}")

        except Exception as e:
            print(f"Processing failed: {str(e)}")

    def _get_user_inputs(self):
        """Get and validate user inputs"""
        while True:
            image_path = input("Enter image path: ").strip()
            if os.path.exists(image_path):
                break
            print(f"File not found: {image_path}")

        default_output = os.path.splitext(image_path)[0] + ".gcode"
        output_file = input(f"Output file [{default_output}]: ").strip()
        return image_path, output_file or default_output

    def _load_and_enhance_image(self, image_path):
        """Load and enhance image details"""
        img = Image.open(image_path).convert('L')
        px_per_mm = self.params['dpi'] / 25.4
        target_size = (
            int(self.params['image_size'][0] * px_per_mm),
            int(self.params['image_size'][1] * px_per_mm)
        )

        img = img.resize(target_size, Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200))
        return ImageEnhance.Contrast(img).enhance(self.params['contrast'])

    def _create_clean_mask(self, img):
        """Create optimized binary mask"""
        img_array = np.array(img)
        thresh = cv2.adaptiveThreshold(
            img_array, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 21, 7)
        kernel = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    def _find_contours(self, binary):
        """Contour detection with careful handling"""
        contours, _ = cv2.findContours(
            binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        px_per_mm = self.params['dpi'] / 25.4
        min_px_area = (self.params['min_feature_size'] * px_per_mm) ** 2
        filtered = []

        for cnt in contours:
            if len(cnt) < 3:
                continue

            try:
                cnt = cnt.astype(np.float32)
                area = cv2.contourArea(cnt)
                if area < min_px_area:
                    continue

                # Gentle simplification
                epsilon = self.params['simplify_tolerance'] * px_per_mm
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                filtered.append(approx)
            except:
                continue

        return filtered

    def _scale_and_sort_contours(self, contours):
        """Convert to mm coordinates with proper sorting"""
        px_per_mm = self.params['dpi'] / 25.4
        scaled = []

        for cnt in contours:
            scaled_cnt = []
            for point in cnt.squeeze():
                x = point[0] / px_per_mm + self.params['x_offset']
                y = (self.params['image_size'][1] - (point[1] / px_per_mm)
                     ) + self.params['y_offset']
                scaled_cnt.append((x, y))
            scaled.append(scaled_cnt)

        # Sort by bounding box position (top-to-bottom, left-to-right)
        scaled.sort(key=lambda c: (min(p[1] for p in c), min(p[0] for p in c)))
        return scaled

    def _write_plotter_gcode(self, contours, output_file):
        """Generate complete G-code with reliable movements"""
        with open(output_file, 'w') as f:
            f.write(f"""; PENCIL PLOTTER G-CODE
G90 G21
G0 Z{self.params['z_initial_position']} F{self.params['z_speed']}
G4 P{self.params['z_change_delay']}
G0 F{self.params['travel_speed']}\n\n""")

            for i, contour in enumerate(contours):
                if len(contour) < 2:
                    continue

                f.write(f"; Contour {i + 1}\n")
                self._write_contour_path(f, contour)

            if self.params['return_to_zero']:
                f.write(f"\nG0 Z{self.params['z_initial_position']}\n")
                f.write(f"G4 P{self.params['z_change_delay']}\n")
                f.write("G0 X0 Y0\n")

            f.write("M30\n")

    def _write_contour_path(self, f, contour):
        """Draw single contour with guaranteed path completion"""
        start = contour[0]
        f.write(f"G0 X{start[0]:.4f} Y{start[1]:.4f} Z{self.params['z_initial_position']}\n")

        # Approach sequence
        f.write(f"G0 Z{self.params['z_lift_position'] + self.params['z_clearance']}\n")
        f.write(f"G4 P{self.params['z_change_delay']}\n")
        f.write(f"G0 Z{self.params['z_lift_position']}\n")
        f.write(f"G4 P{self.params['z_change_delay']}\n")
        f.write(f"G1 Z{self.params['z_drawing_position']} F{self.params['z_speed']}\n")
        f.write(f"G4 P{self.params['z_change_delay']}\n")

        # Drawing moves
        f.write(f"G1 F{self.params['draw_speed']}\n")
        for point in contour[1:]:
            f.write(f"X{point[0]:.4f} Y{point[1]:.4f}\n")
        f.write(f"X{contour[0][0]:.4f} Y{contour[0][1]:.4f}\n")  # Force close path

        # Retract sequence
        f.write(f"G0 Z{self.params['z_lift_position']}\n")
        f.write(f"G4 P{self.params['z_change_delay']}\n")
        f.write(f"G0 Z{self.params['z_lift_position'] + self.params['z_clearance']}\n")
        f.write(f"G4 P{self.params['z_change_delay']}\n\n")


if __name__ == "__main__":
    generator = PencilPlotterGenerator()
    generator.process_image_to_gcode()

