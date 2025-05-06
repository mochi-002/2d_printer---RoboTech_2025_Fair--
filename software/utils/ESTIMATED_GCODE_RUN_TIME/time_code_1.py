import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class GCodeState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0
    f: float = 1000.0  # Default feedrate (G0 rapid speed)
    s: float = 0.0
    t: Optional[int] = None
    relative: bool = False  # G90/G91 mode
    ijk_relative: bool = True  # G90.1/G91.1 arc mode
    offset_g92: Dict[str, float] = None  # G92 offsets

    def __post_init__(self):
        self.offset_g92 = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'e': 0.0}

class GCodeParser:
    def __init__(self):
        self.state = GCodeState()
        self.total_time = 0.0  # minutes
        self.total_distance = 0.0  # mm
        self.arc_segments = 20  # Same as OpenBuilds

    def parse(self, gcode: str) -> float:
        for line in gcode.splitlines():
            self._parse_line(line.strip())
        return self.total_time

    def _parse_line(self, line: str):
        # Remove comments and normalize
        line = re.sub(r'\(.*?\)|;.*', '', line).strip()
        if not line:
            return

        # Handle special commands first
        if line.upper() in ('G90', 'G91', 'G90.1', 'G91.1', 'G20', 'G21'):
            self._handle_mode_command(line.upper())
            return

        # Parse command and args
        tokens = re.findall(r'([GMT][0-9.]+)|([XYZEFSIJK][-+]?[0-9.]+)', line, re.IGNORECASE)
        if not tokens:
            return

        cmd = tokens[0][0].upper() if tokens[0][0] else None
        args = {}
        for token in tokens[1:]:
            if token[1]:  # It's an arg (X/Y/Z/etc)
                key = token[1][0].lower()
                value = float(token[1][1:])
                args[key] = value

        # Handle motion commands
        if cmd in ('G0', 'G1', 'G2', 'G3'):
            self._handle_motion(cmd, args)

    def _handle_mode_command(self, cmd: str):
        if cmd == 'G90':
            self.state.relative = False
        elif cmd == 'G91':
            self.state.relative = True
        elif cmd == 'G90.1':
            self.state.ijk_relative = False
        elif cmd == 'G91.1':
            self.state.ijk_relative = True
        elif cmd == 'G20':
            print("Warning: Inch mode not fully implemented - assuming mm")
        elif cmd == 'G21':
            pass  # Default is mm

    def _handle_motion(self, cmd: str, args: Dict[str, float]):
        # Get target position with G92 offsets
        p1 = (self.state.x, self.state.y, self.state.z)
        p2 = list(p1)
        
        for axis in ['x', 'y', 'z']:
            if axis in args:
                p2['xyz'.index(axis)] = (
                    args[axis] + self.state.offset_g92[axis] if not self.state.relative 
                    else p2['xyz'.index(axis)] + args[axis] + self.state.offset_g92[axis]
                )

        # Update feedrate if specified
        feedrate = args.get('f', self.state.f)
        
        # Calculate distance and time
        if cmd in ('G0', 'G1'):
            distance = math.sqrt(sum((p2[i]-p1[i])**2 for i in range(3)))
            time_min = self._calculate_move_time(distance, feedrate, is_rapid=(cmd == 'G0'))
            self._update_totals(distance, time_min)
        elif cmd in ('G2', 'G3'):
            self._handle_arc_move(p1, p2, args, feedrate, cmd == 'G2')

        # Update state
        self.state.x, self.state.y, self.state.z = p2
        self.state.f = feedrate
        if 'e' in args:
            self.state.e = args['e'] if not self.state.relative else self.state.e + args['e']

    def _handle_arc_move(self, p1: Tuple[float, float, float], p2: List[float], args: Dict[str, float], feedrate: float, clockwise: bool):
        # Get arc center (I/J/K or R format)
        if 'r' in args:
            center = self._calculate_center_from_radius(p1, p2, args['r'], clockwise)
        else:
            center = [
                args.get('i', 0.0) + (p1[0] if self.state.ijk_relative else 0.0),
                args.get('j', 0.0) + (p1[1] if self.state.ijk_relative else 0.0),
                args.get('k', 0.0) + (p1[2] if self.state.ijk_relative else 0.0)
            ]

        # Generate arc segments
        arc_points = self._generate_arc_points(p1, p2, center, clockwise)
        
        # Calculate time for each segment
        segment_dist = math.sqrt(sum((p2[i]-p1[i])**2 for i in range(3))) / self.arc_segments
        for _ in arc_points:
            time_min = self._calculate_move_time(segment_dist, feedrate)
            self._update_totals(segment_dist, time_min)

    def _calculate_move_time(self, distance: float, feedrate: float, is_rapid: bool = False) -> float:
        if distance <= 0:
            return 0.0
        
        # OpenBuilds uses 1000mm/min default for G0, 100mm/min for G1 if no feedrate
        effective_feedrate = feedrate if feedrate > 0 else (1000.0 if is_rapid else 100.0)
        time_min = distance / effective_feedrate
        
        # Apply OpenBuilds' acceleration factor
        return time_min * 1.32

    def _update_totals(self, distance: float, time_min: float):
        self.total_distance += distance
        self.total_time += time_min

    def _calculate_center_from_radius(self, p1, p2, radius, clockwise):
        # Simplified radius-based arc center calculation
        # (Matches OpenBuilds' logic)
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        chord_length = math.sqrt(dx**2 + dy**2)
        
        if chord_length == 0:
            return [p1[0], p1[1], p1[2]]
        
        mid_x, mid_y = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
        perpendicular = math.sqrt(radius**2 - (chord_length/2)**2) * (-1 if clockwise else 1)
        
        center_x = mid_x + perpendicular * (-dy/chord_length)
        center_y = mid_y + perpendicular * (dx/chord_length)
        
        return [center_x, center_y, p1[2]]

    def _generate_arc_points(self, p1, p2, center, clockwise):
        # Generate approximate arc points (OpenBuilds uses 20 segments)
        points = []
        start_angle = math.atan2(p1[1]-center[1], p1[0]-center[0])
        end_angle = math.atan2(p2[1]-center[1], p2[0]-center[0])
        radius = math.sqrt((p1[0]-center[0])**2 + (p1[1]-center[1])**2)
        
        if clockwise:
            if end_angle >= start_angle:
                end_angle -= 2 * math.pi
        else:
            if end_angle <= start_angle:
                end_angle += 2 * math.pi
        
        angle_step = (end_angle - start_angle) / self.arc_segments
        for i in range(1, self.arc_segments + 1):
            angle = start_angle + i * angle_step
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = p1[2] + (p2[2]-p1[2]) * (i/self.arc_segments)
            points.append((x, y, z))
        
        return points

def time_convert(minutes: float) -> str:
    """Convert minutes to hh:mm:ss format like OpenBuilds"""
    total_seconds = int(minutes * 60)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def main():
    print("OpenBuilds G-code Time Estimator")
    print("-------------------------------")
    
    while True:
        filename = input("\nEnter G-code filename (or 'quit' to exit): ").strip()
        
        if filename.lower() in ('quit', 'exit'):
            break
            
        try:
            with open(filename, 'r') as f:
                gcode = f.read()
                
            parser = GCodeParser()
            total_time = parser.parse(gcode)
            
            print("\nResults:")
            print(f"Estimated time: {time_convert(total_time)}")
            print(f"Total distance: {parser.total_distance:.2f} mm")
            print(f"Lines processed: {len(gcode.splitlines())}")

            
            
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found. Please try again.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()