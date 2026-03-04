The Tip/Tilt Focus Sweep Print is a multi-region calibration pattern used to determine both optimal focus and platform tip/tilt offsets. This pattern analyzes five discrete points across the build area to detect and correct angular misalignments (**Tip** and **Tilt**).

## Print Layout & Orientation

The print consists of five distinct measurement regions: one in the **Center**, and four located in the **+/- Tip** and **+/- Tilt** directions.

### Orientation Markers

To ensure the print is analyzed in the correct direction:

- **Corner Symbols:** The **+/+** and **-/-** corners of the print are physically marked with symbols.
- **Coordinate System:** For the OS1 series printer, the tip axis maps to the long axis of the print.

## How the Print Works

Each of the five regions contains a **5×5** grid (25 squares total). Unlike a standard sweep that varies only by column, these regions provide a concentrated look at focal shifts.

- **Step Size:** Each square represents a focal offset of $\pm 12 \times \text{step size}$.
- **The Center Region:**  Functions as a compressed focus print to establish your primary focal baseline.
- **The Peripheral Regions:** Used specifically to calculate the optical missalignment of the projected image. 

## Calibration Steps

To calibrate your system, follow this three-step process:

### 1. Identify the Best Square

Inspect each of the five regions under magnification. Identify the square exhibiting the highest clarity, sharpest edges, and best feature resolution.

### 2. Record the Values

Assign each "best square" its corresponding numerical offset (e.g., if the best square is 3 steps in the positive direction, your value is $+3$). In the grid, the top left corner is negative the bottom right is positive.

### 3. Calculate the Offsets

Use the difference between opposing regions to determine your mechanical adjustment needs.

### Tip Offset Calculation

Determine the tilt along the Y-axis:$$\text{Tip Offset} = (\text{Best Square}_{+Tip}) - (\text{Best Square}_{-Tip})$$

### Tilt Offset Calculation

Determine the tilt along the X-axis:$$\text{Tilt Offset} = (\text{Best Square}_{+Tilt}) - (\text{Best Square}_{-Tilt})$$

