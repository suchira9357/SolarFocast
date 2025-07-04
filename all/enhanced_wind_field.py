# enhanced_wind_field.py
"""
Enhanced Wind Field for Solar Farm Simulation
Provides realistic multi-layer wind patterns
"""
import numpy as np
import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List
import sim_config as CFG

@dataclass
class WindFieldConfig:
    """Configuration parameters for WindField."""
    domain_size: int = CFG.DOMAIN_SIZE_M  # Physical size in pixels
    grid_resolution: int = CFG.WIND_GRID  # Grid cells across domain
    base_wind_speed: float = CFG.BASE_WIND_SPEED  # Base wind speed (m/s)
    wind_direction: float = CFG.BASE_WIND_DIRECTION  # Wind direction (degrees)
    num_layers: int = 3  # Number of atmospheric layers
    layer_heights: List[float] = None  # Layer boundaries in km
    layer_speed_factors: List[float] = None  # Speed multipliers per layer
    layer_direction_offsets: List[float] = None  # Direction offsets per layer

class EnhancedWindField:
    """Multi-layer wind field with altitude-dependent behavior."""
    def __init__(self, config=None):
        """Initialize the wind field."""
        self.config = config or WindFieldConfig()
        self.base_direction = self.config.wind_direction
        
        # Set up altitude layers if not provided
        if self.config.layer_heights is None:
            self.config.layer_heights = CFG.LAYER_HEIGHTS
        if self.config.layer_speed_factors is None:
            self.config.layer_speed_factors = CFG.LAYER_SPEED_FACTORS
        if self.config.layer_direction_offsets is None:
            self.config.layer_direction_offsets = CFG.LAYER_DIRECTION_OFFSETS
            
        # Create a grid for each layer
        self.grid = self.config.grid_resolution
        self.num_layers = len(self.config.layer_speed_factors)
        
        # Initialize cells for each layer
        self.cells = np.empty((self.num_layers, self.grid, self.grid, 2), dtype=np.float32)
        
        # Initialize each layer with its own wind pattern
        for layer in range(self.num_layers):
            # Base parameters for this layer
            base_speed = self.config.base_wind_speed * self.config.layer_speed_factors[layer]
            base_direction = (self.config.wind_direction + self.config.layer_direction_offsets[layer]) % 360
            
            # Add spatial variations
            for i in range(self.grid):
                for j in range(self.grid):
                    # Apply some natural variation
                    # More variation in lower layers (boundary effects)
                    variation_factor = 1.0 / (layer + 1)
                    
                    # Speed variations
                    speed_variation = np.random.normal(0, 0.05 * variation_factor * base_speed)
                    speed = base_speed + speed_variation
                    
                    # Direction variations
                    dir_variation = np.random.normal(0, 3.0 * variation_factor)
                    direction = (base_direction + dir_variation) % 360
                    
                    # Store in cells
                    self.cells[layer, i, j, 0] = speed
                    self.cells[layer, i, j, 1] = direction
                    
        # Precompute vectors for interpolation
        self.vectors_x = np.zeros((self.num_layers, self.grid, self.grid), dtype=np.float32)
        self.vectors_y = np.zeros((self.num_layers, self.grid, self.grid), dtype=np.float32)
        self._precompute_vectors()
        
        # Keep track of previous vectors for smooth transitions
        self.prev_vectors_x = self.vectors_x.copy()
        self.prev_vectors_y = self.vectors_y.copy()
        
        # Temporal interpolation
        self.last_update_time = time.time()
        self.last_update_frame = 0
        self.interpolation_factor = 0.0
        
        print(f"Created multi-layer wind field with {self.num_layers} layers:")
        for i in range(self.num_layers):
            if i < len(self.config.layer_heights) - 1:
                height_range = f"{self.config.layer_heights[i]:.1f}-{self.config.layer_heights[i+1]:.1f}"
            else:
                height_range = f"{self.config.layer_heights[i]:.1f}+"
            layer_speed = self.config.base_wind_speed * self.config.layer_speed_factors[i]
            layer_direction = (self.config.wind_direction + self.config.layer_direction_offsets[i]) % 360
            print(f"  Layer {i}: {height_range} km, Speed: {layer_speed:.1f} m/s, Direction: {layer_direction:.1f}°")
            
    def _precompute_vectors(self):
        """Precompute wind vectors for efficient interpolation."""
        for layer in range(self.num_layers):
            for i in range(self.grid):
                for j in range(self.grid):
                    speed = self.cells[layer, i, j, 0]
                    direction_rad = np.radians(self.cells[layer, i, j, 1])
                    self.vectors_x[layer, i, j] = speed * np.cos(direction_rad)
                    self.vectors_y[layer, i, j] = speed * np.sin(direction_rad)
                    
    def step(self, frame_idx=None):
        """Update wind field (smoothly over time)."""
        current_time = time.time()
        
        # Check if it's time to update based on real seconds
        if frame_idx != self.last_update_frame and current_time - self.last_update_time >= CFG.WIND_UPDATE_SEC:
            self.last_update_time = current_time
            self.last_update_frame = frame_idx
            self._update_wind_field()
            
        # Calculate interpolation factor (0 to 1) since last update
        elapsed = current_time - self.last_update_time
        self.interpolation_factor = min(1.0, elapsed / CFG.WIND_UPDATE_SEC)
        
    def _update_wind_field(self):
        """Apply subtle changes to the wind field."""
        # Save current vectors for smooth transition
        self.prev_vectors_x = self.vectors_x.copy()
        self.prev_vectors_y = self.vectors_y.copy()
        
        # Update each layer
        for layer in range(self.num_layers):
            # Smaller changes at higher altitudes (more stable)
            variation_factor = 1.0 / (layer + 1)
            
            # Very subtle changes to the wind field
            speed_change = np.random.normal(0, 0.01 * variation_factor, self.cells[layer, ..., 0].shape)
            self.cells[layer, ..., 0] += speed_change
            
            # Ensure minimum speeds
            min_speed = self.config.base_wind_speed * self.config.layer_speed_factors[layer] * 0.5
            self.cells[layer, ..., 0] = np.clip(
                self.cells[layer, ..., 0], 
                min_speed, 
                self.config.base_wind_speed * self.config.layer_speed_factors[layer] * 1.5
            )
            
            # Even gentler direction changes
            direction_change = np.random.normal(0, 0.02 * variation_factor, self.cells[layer, ..., 1].shape)
            self.cells[layer, ..., 1] = (self.cells[layer, ..., 1] + direction_change) % 360
            
        # Recompute vectors
        self._precompute_vectors()
        
    def get_velocity_at_altitude(self, altitude_km):
        """
        Get wind velocity at a specific altitude.
        
        Args:
            altitude_km: Altitude in kilometers
            
        Returns:
            Tuple of (vx, vy) in km/h
        """
        # Determine layer index based on altitude
        layer_index = 0
        for i in range(len(self.config.layer_heights) - 1):
            if altitude_km >= self.config.layer_heights[i] and altitude_km < self.config.layer_heights[i+1]:
                layer_index = i
                break
        
        # Use highest layer for anything above the top boundary
        if altitude_km >= self.config.layer_heights[-1]:
            layer_index = len(self.config.layer_heights) - 2
        
        # Get speed for this layer
        spd_ms = self.config.base_wind_speed * self.config.layer_speed_factors[layer_index]
        spd_kph = spd_ms * 3.6  # Convert m/s to km/h
        
        # Force direction to be BASE_WIND_DIRECTION
        direction = CFG.BASE_WIND_DIRECTION + CFG.LAYER_DIRECTION_OFFSETS[layer_index]
        vx = spd_kph * math.cos(math.radians(direction))
        vy = spd_kph * math.sin(math.radians(direction))
        
        return vx, vy
        
    def sample(self, x: float, y: float, z: Optional[float] = None) -> Tuple[float, float]:
        """
        Sample the wind field at a specific location and altitude.
        
        Args:
            x, y: Position in domain coordinates
            z: Altitude in kilometers (default: 0)
        
        Returns:
            Tuple of (wind_speed, wind_direction)
        """
        # Default z to middle layer if not specified
        if z is None:
            z = 0.5  # Default altitude in km
            
        # Determine which layer to use
        layer_idx = 0
        for i in range(len(self.config.layer_heights) - 1):
            if z >= self.config.layer_heights[i] and z < self.config.layer_heights[i+1]:
                layer_idx = i
                break
                
        # Use highest layer for anything above the top boundary
        if z >= self.config.layer_heights[-1]:
            layer_idx = len(self.config.layer_heights) - 2
            
        # Bilinear interpolation within the layer's grid
        size = self.config.domain_size
        g = self.grid
        
        # Clamp coordinates to valid range
        x = max(0.01, min(x, size - 0.01))
        y = max(0.01, min(y, size - 0.01))
        
        # Calculate grid cell and interpolation factors
        fx = (x / size) * (g - 1.01)
        fy = (y / size) * (g - 1.01)
        ix = int(fx)
        iy = int(fy)
        ix = max(0, min(ix, g - 2))
        iy = max(0, min(iy, g - 2))
        tx = fx - ix
        ty = fy - iy
        ix1 = ix + 1
        iy1 = iy + 1
        
        # Interpolate current vectors
        vx00 = self.vectors_x[layer_idx, iy, ix]
        vx10 = self.vectors_x[layer_idx, iy, ix1]
        vx01 = self.vectors_x[layer_idx, iy1, ix]
        vx11 = self.vectors_x[layer_idx, iy1, ix1]
        vx0 = (1 - tx) * vx00 + tx * vx10
        vx1 = (1 - tx) * vx01 + tx * vx11
        vx_curr = (1 - ty) * vx0 + ty * vx1
        
        vy00 = self.vectors_y[layer_idx, iy, ix]
        vy10 = self.vectors_y[layer_idx, iy, ix1]
        vy01 = self.vectors_y[layer_idx, iy1, ix]
        vy11 = self.vectors_y[layer_idx, iy1, ix1]
        vy0 = (1 - tx) * vy00 + tx * vy10
        vy1 = (1 - tx) * vy01 + tx * vy11
        vy_curr = (1 - ty) * vy0 + ty * vy1
        
        # Interpolate previous vectors for temporal smoothing
        vx00 = self.prev_vectors_x[layer_idx, iy, ix]
        vx10 = self.prev_vectors_x[layer_idx, iy, ix1]
        vx01 = self.prev_vectors_x[layer_idx, iy1, ix]
        vx11 = self.prev_vectors_x[layer_idx, iy1, ix1]
        vx0 = (1 - tx) * vx00 + tx * vx10
        vx1 = (1 - tx) * vx01 + tx * vx11
        vx_prev = (1 - ty) * vx0 + ty * vx1
        
        vy00 = self.prev_vectors_y[layer_idx, iy, ix]
        vy10 = self.prev_vectors_y[layer_idx, iy, ix1]
        vy01 = self.prev_vectors_y[layer_idx, iy1, ix]
        vy11 = self.prev_vectors_y[layer_idx, iy1, ix1]
        vy0 = (1 - tx) * vy00 + tx * vy10
        vy1 = (1 - tx) * vy01 + tx * vy11
        vy_prev = (1 - ty) * vy0 + ty * vy1
        
        # Temporal interpolation
        t = self.interpolation_factor
        vx = vx_prev * (1 - t) + vx_curr * t
        vy = vy_prev * (1 - t) + vy_curr * t
        
        # Convert back to speed and direction
        speed = math.hypot(vx, vy)
        direction = (math.degrees(math.atan2(vy, vx)) + 360) % 360
        
        return speed, direction
        
    def vector(self, t_min: float) -> Tuple[float, float]:
        """
        Return (dx_km_per_min, dy_km_per_min) at sim-time t [minutes].
        Compatibility method for cloud_simulation.py
        
        Args:
            t_min: Time in minutes since simulation start
            
        Returns:
            Tuple (dx, dy) representing wind vector in km/min
        """
        # Sample wind at the center of the domain with default altitude
        speed, direction = self.sample(CFG.DOMAIN_SIZE_M/2, CFG.DOMAIN_SIZE_M/2, 1.0)
        
        # Convert m/s to km/min
        speed_km_min = speed * 60 / 1000
        
        # Convert to vector components
        dir_rad = math.radians(direction)
        dx = speed_km_min * math.cos(dir_rad)
        dy = speed_km_min * math.sin(dir_rad)
        
        return dx, dy
        
    def vector_at_altitude(self, t_min: float, altitude_idx: int) -> Tuple[float, float]:
        """
        Return wind vector at a specific altitude layer.
        Compatibility method for cloud_simulation.py
        
        Args:
            t_min: Time in minutes
            altitude_idx: Altitude layer index
            
        Returns:
            Tuple (dx, dy) representing wind vector in km/min
        """
        # Map altitude_idx to actual altitude in km
        if altitude_idx >= len(CFG.LAYER_HEIGHTS):
            altitude = CFG.LAYER_HEIGHTS[-1]
        else:
            altitude = CFG.LAYER_HEIGHTS[altitude_idx]
        
        # Sample wind at this altitude
        speed, direction = self.sample(CFG.DOMAIN_SIZE_M/2, CFG.DOMAIN_SIZE_M/2, altitude)
        
        # Convert m/s to km/min
        speed_km_min = speed * 60 / 1000
        
        # Convert to vector components
        dir_rad = math.radians(direction)
        dx = speed_km_min * math.cos(dir_rad)
        dy = speed_km_min * math.sin(dir_rad)
        
        return dx, dy
        
    def get_dominant_flow(self, layer: int = 1) -> Tuple[float, float]:
        """
        Get the dominant flow direction and speed for a specific layer.
        
        Args:
            layer: Layer index (default: 1 - low layer)
            
        Returns:
            Tuple of (avg_speed, avg_direction)
        """
        layer = max(0, min(layer, self.num_layers - 1))
        
        # Calculate average vectors
        avg_vx = np.mean(self.vectors_x[layer])
        avg_vy = np.mean(self.vectors_y[layer])
        
        # Convert to speed and direction
        avg_speed = math.hypot(avg_vx, avg_vy)
        avg_direction = (math.degrees(math.atan2(avg_vy, avg_vx)) + 360) % 360
        
        return avg_speed, avg_direction

def get_global_wind_vector():
    """
    Return (vx, vy) vector from global wind speed and direction.
    
    Returns:
        Tuple of (vx, vy) in km/h representing the wind vector
    """
    # Get wind speed and direction from config
    speed = CFG.DEFAULT_WIND_SPEED_KMH
    direction = CFG.DEFAULT_WIND_DIRECTION_DEG
    
    # Convert to vector components
    rad = math.radians(direction)
    vx = speed * math.cos(rad)
    vy = speed * math.sin(rad)
    
    return vx, vy