import pycuda.autoinit
import pycuda.driver as drv
import numpy as np
import time

from pycuda.compiler import SourceModule


mod = SourceModule("""
__global__ void quadratic_difference(int *correlations, int N, float *x, float *y, float *z, float *ct)
{
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    unsigned int j = blockIdx.y * blockDim.y + threadIdx.y;

    if (i >= N || j < i || j >= N) return;

    unsigned int pos1 = i * N + j;
    unsigned int pos2 = j * N + i;

    if (j==i){
      correlations[pos1] = 1;
      correlations[pos2] = 1;
      return;
    }

    float diffct = ct[i] - ct[j];
    float diffx  = x[i] - x[j];
    float diffy  = y[i] - y[j];
    float diffz  = z[i] - z[j];


    if (diffct * diffct < diffx * diffx + diffy * diffy + diffz * diffz){ 
      correlations[pos1] = 1;
      correlations[pos2] = 1;
    }
    else{
      correlations[pos1] = 0;
      correlations[pos2] = 0;
   }

}
""")

quadratic_difference= mod.get_function("quadratic_difference")

N = 4500

x = np.random.randn(N).astype(np.float32)
y = np.random.randn(N).astype(np.float32)
z = np.random.randn(N).astype(np.float32)
ct = np.random.randn(N).astype(np.float32)

x_gpu = drv.mem_alloc(x.nbytes)
y_gpu = drv.mem_alloc(y.nbytes)
z_gpu = drv.mem_alloc(z.nbytes)
ct_gpu = drv.mem_alloc(ct.nbytes)

drv.memcpy_htod(x_gpu, x)
drv.memcpy_htod(y_gpu, y)
drv.memcpy_htod(z_gpu, z)
drv.memcpy_htod(ct_gpu, ct)

correlations = np.empty((N, N), np.int32)
correlations_gpu = drv.mem_alloc(correlations.nbytes)

block_size = 1024
block_size_x = int(np.sqrt(block_size))
block_size_y = int(np.sqrt(block_size))

problem_size = N 

gridx = int(np.ceil(problem_size/block_size_x))
gridy = int(np.ceil(problem_size/block_size_y))

# create two timers so we can speed-test each approach
start = drv.Event()
end = drv.Event()

start.record() # start timing

quadratic_difference(
        correlations_gpu, np.int32(N), x_gpu, y_gpu, z_gpu, ct_gpu, 
        block=(block_size_x, block_size_y, 1), grid=(gridx, gridy))

end.record() # end timing
# calculate the run length
end.synchronize()
secs = start.time_till(end)*1e-3

drv.memcpy_dtoh(correlations, correlations_gpu)

print()
print('Times taken is {0:.2e}s.'.format(secs))
print()
correlations = correlations.reshape(N, N)
print('correlations = ', correlations)
print()
print('correlations.max() = {0}, correlations.argmax() = {1}'.format(correlations.max(), np.unravel_index(correlations.argmax(), correlations.shape)))
# check for symmetry.
print()
print('Symmetry check, this should be zero: {0}'.format(np.sum(np.abs(correlations - correlations.T))))

check = np.identity(correlations.shape[0], correlations.dtype)

# Checkif output is correct.
for i in range(check.shape[0]):
    for j in range(i+1, check.shape[1]):
        if (ct[i]-ct[j])**2 < (x[i]-x[j])**2  + (y[i] - y[j])**2 + (z[i] - z[j])**2:
          check[i, j] = 1
          check[j, i] = check[i, j]

print()
print()
print('check = ', check)
print()
print('check.max() = {0}'.format(check.max()))
print()
print('Symmetry check, this should be zero: {0}'.format(np.sum(np.abs(check - check.T))))
print()
print()
print()
print('This should be close to zero: {0}'.format(np.max(np.abs(check - correlations))))
print()
print('check - correlations = ', check -correlations)
