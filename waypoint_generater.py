import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import csv
import os
import yaml
import cv2

# path yaml and (pgm or png)
yaml_file = os.path.join("/home/your_map.yaml")
map_path = os.path.join("/home/your_map.pgm")

class WaypointCreator:
   def __init__(self, map_name=None):
       self.points = []
       self.velocities = []
       self.default_velocity = 1.0
       self.fig, self.ax = plt.subplots(figsize=(10, 10))
       self.map_name = map_name
       
       # Current directory path
       module_path = os.path.dirname(os.path.abspath(__file__))
       
       
       try:
           with open(yaml_file, 'r') as stream:
               map_yaml = yaml.safe_load(stream)
           scale = map_yaml["resolution"]
           offset_x = map_yaml["origin"][0]
           offset_y = map_yaml["origin"][1]
           
           # Load map image
           input_img = cv2.imread(map_path, cv2.IMREAD_GRAYSCALE)
           h, w = input_img.shape[:2]
           
           # Image preprocessing
           self.map_img = ~input_img  # Invert black and white
           
           print(f"Map loaded successfully: size={w}x{h}, scale={scale}, offset=({offset_x},{offset_y})")
           self.ax.imshow(input_img, cmap='gray', extent=[offset_x, offset_x + w*scale, 
                                                        offset_y, offset_y + h*scale])
           
       except Exception as e:
           print(f"Warning: Could not load map: {e}")
      
       
       # Connect mouse/keyboard events
       self.fig.canvas.mpl_connect('button_press_event', self._on_click)
       self.fig.canvas.mpl_connect('key_press_event', self._on_key)
       
       self.ax.set_title(f'Map: {map_name}\nLeft click: Add point, Right click: Remove last point\n'
                        'Up/Down arrows: Adjust default velocity\n'
                        'Press Enter to save and quit')
   
   def _on_click(self, event):
       if event.inaxes != self.ax:
           return
       
       if event.button == 1:  # Left click: Add point
           self.points.append((event.xdata, event.ydata))
           self.velocities.append(self.default_velocity)
           self._update_plot()
       
       elif event.button == 3 and self.points:  # Right click: Remove last point
           self.points.pop()
           self.velocities.pop()
           self._update_plot()
   
   def _on_key(self, event):
       if event.key == 'up':
           self.default_velocity += 0.1
           print(f"Default velocity: {self.default_velocity:.1f}")
       elif event.key == 'down':
           self.default_velocity = max(0.1, self.default_velocity - 0.1)
           print(f"Default velocity: {self.default_velocity:.1f}")
       elif event.key == 'enter':
           plt.close()
   
   def _update_plot(self):
       self.ax.clear()
       
       # Redraw map
       module_path = os.path.dirname(os.path.abspath(__file__))
       try:
           with open(yaml_file, 'r') as stream:
               map_yaml = yaml.safe_load(stream)
           scale = map_yaml["resolution"]
           offset_x = map_yaml["origin"][0]
           offset_y = map_yaml["origin"][1]
           
           input_img = cv2.imread(map_path, cv2.IMREAD_GRAYSCALE)
           h, w = input_img.shape[:2]
           self.ax.imshow(input_img, cmap='gray', extent=[offset_x, offset_x + w*scale, 
                                                        offset_y, offset_y + h*scale])
       except Exception as e:
           pass
           
       # Redraw centerline
       try:
           centerline_path = os.path.join(module_path, "outputs", f"{self.map_name}/centerline")
           centerline_data = np.loadtxt(centerline_path, delimiter=',', skiprows=1)
           self.ax.plot(centerline_data[:, 0], centerline_data[:, 1], 'k--', alpha=0.5, label='centerline')
       except Exception as e:
           pass
       
       if len(self.points) > 0:
           points = np.array(self.points)
           self.ax.plot(points[:, 0], points[:, 1], 'b-', linewidth=2)
           self.ax.scatter(points[:, 0], points[:, 1], c='red', s=50)
           for i, (point, vel) in enumerate(zip(points, self.velocities)):
               self.ax.annotate(f'{i}:{vel:.1f}', (point[0], point[1]))
       
       self.ax.grid(True)
       self.ax.set_title(f'Map: {self.map_name}\nLeft click: Add point, Right click: Remove last point\n'
                       'Up/Down arrows: Adjust default velocity\n'
                       'Press Enter to save and quit')
       self.fig.canvas.draw()

   def save_traj_race_cl(self, output_dir):
       if not self.points:
           print("No points to save!")
           return
       
       points = np.array(self.points)
       n_points = len(points)
       
       # Calculate distance (s)
       diffs = np.diff(points, axis=0)
       segment_lengths = np.sqrt(np.sum(diffs**2, axis=1))
       s_vals = np.concatenate(([0], np.cumsum(segment_lengths)))
       
       # Calculate direction (psi)
       psi = np.zeros(n_points)
       for i in range(n_points):
           next_idx = (i + 1) % n_points
           dx = points[next_idx, 0] - points[i, 0]
           dy = points[next_idx, 1] - points[i, 1]
           psi[i] = np.arctan2(dy, dx)
       
       # Calculate curvature (kappa)
       kappa = np.zeros(n_points)
       for i in range(n_points):
           prev_idx = (i - 1) % n_points
           next_idx = (i + 1) % n_points
           
           x1, y1 = points[prev_idx]
           x2, y2 = points[i]
           x3, y3 = points[next_idx]
           
           d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
           if abs(d) > 1e-10:
               ux = ((x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)) / d
               uy = ((x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)) / d
               r = np.sqrt((x2 - ux)**2 + (y2 - uy)**2)
               kappa[i] = 1/r if r > 0 else 0
       
       # Save CSV file
       os.makedirs(output_dir, exist_ok=True)
       filename = os.path.join(output_dir, 'traj_race_cl.csv')
       
       with open(filename, 'w', newline='') as f:
           writer = csv.writer(f)
           
           # Write data
           for i in range(n_points):
               x, y = points[i]
               vx = self.velocities[i]
               ax = 0.0
               writer.writerow([s_vals[i], x, y, psi[i], kappa[i], vx, ax])
           
           # Close the trajectory
           writer.writerow([s_vals[-1], points[0][0], points[0][1], 
                         psi[0], kappa[0], self.velocities[0], 0.0])
       
       print(f"Saved trajectory to {filename}")

def create_trajectory():
    module = os.path.dirname(os.path.abspath(__file__))
   
    try:
        with open(yaml_file, 'r') as stream:
            parsed_yaml = yaml.safe_load(stream)
            print("Loaded configuration from params.yaml")
    except Exception as e:
        print(f"Error loading config file: {e}")
        return
   
    # Use map name without the .pgm extension from the 'image' value
    image_name = parsed_yaml["image"].split('.')[0]  
    print(f"Using map: {image_name}")
   
    output_dir = os.path.join(module, "outputs", image_name)
    os.makedirs(output_dir, exist_ok=True)
   
    creator = WaypointCreator(map_name=image_name)
    plt.show()
   
    creator.save_traj_race_cl(output_dir)

if __name__ == "__main__":
   create_trajectory()

