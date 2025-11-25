import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  # needed for 3D projection

points = [
    (2057.94, -455.529, 2583),
    (2057.94, -460.725, 2592),
    (2057.94, -465.921, 2601),
    (2057.94, -471.117, 2610),
    (2057.94, -476.314, 2619),
    (2057.94, -478.046, 2622),
]

xs, ys, zs = zip(*points)

fig = plt.figure()
ax = fig.add_subplot(111, projection="3d")
ax.scatter(xs, ys, zs, color="crimson", s=50, depthshade=True)
ax.plot(xs, ys, zs, color="gray", alpha=0.6)

for idx, (x, y, z) in enumerate(points):
    ax.text(x, y, z, f" {idx}", fontsize=9, color="black")

ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.set_title("Point cloud (6 points)")
ax.view_init(elev=20, azim=35)  # tweak angles if you like

plt.tight_layout()
plt.show()

