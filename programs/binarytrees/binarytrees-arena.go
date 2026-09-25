// binary-trees with a pre-allocated, pointer-free node arena.
//
// go-bench variant, NOT eligible for the Benchmarks Game (its rules reject
// hand-written memory pools). It exists to show what the same work costs when
// the garbage collector is taken out of the picture, as the C (apr pools) and
// Rust (arena crates) entries do with library pools.
//
// Every tree is still built node by node, linked, and walked recursively; only
// the storage differs:
//   - nodes live in a []node owned by one worker and reused for every tree;
//   - children are int32 indices, not pointers, so the slice is "noscan" and
//     the GC never traverses it;
//   - after start-up there is no allocation at all;
//   - each worker's arena header has its own cache lines (no false sharing).
//
// Output is identical to the reference program.

package main

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
)

const minDepth = 4

type node struct{ left, right int32 } // -1 = no child

// Each worker's arena header is written on every node; pad it to its own
// cache lines so workers don't false-share (24-byte headers would otherwise
// sit side by side in one 64-byte line).
type arena struct {
	nodes []node
	_     [128 - 24]byte
}

func newArena(maxDepth int) *arena {
	return &arena{nodes: make([]node, 0, 1<<uint(maxDepth+1))}
}

func (a *arena) reset() { a.nodes = a.nodes[:0] }

// bottomUp builds a complete tree of the given depth, returning its root index.
func (a *arena) bottomUp(depth int) int32 {
	i := int32(len(a.nodes))
	a.nodes = append(a.nodes, node{-1, -1})
	if depth > 0 {
		l := a.bottomUp(depth - 1)
		r := a.bottomUp(depth - 1)
		a.nodes[i] = node{l, r}
	}
	return i
}

func (a *arena) check(i int32) int {
	n := a.nodes[i]
	if n.left < 0 {
		return 1
	}
	return 1 + a.check(n.left) + a.check(n.right)
}

func main() {
	n := 0
	if len(os.Args) > 1 {
		n, _ = strconv.Atoi(os.Args[1])
	}
	maxDepth := n
	if minDepth+2 > n {
		maxDepth = minDepth + 2
	}

	{
		a := newArena(maxDepth + 1)
		root := a.bottomUp(maxDepth + 1)
		fmt.Printf("stretch tree of depth %d\t check: %d\n", maxDepth+1, a.check(root))
	}

	longLived := newArena(maxDepth)
	longRoot := longLived.bottomUp(maxDepth)

	workers := runtime.NumCPU()
	arenas := make([]*arena, workers)
	for w := range arenas {
		arenas[w] = newArena(maxDepth)
	}

	for depth := minDepth; depth <= maxDepth; depth += 2 {
		iterations := 1 << uint(maxDepth-depth+minDepth)
		sums := make([]int, workers)
		var wg sync.WaitGroup
		for w := 0; w < workers; w++ {
			wg.Add(1)
			go func(w int) {
				defer wg.Done()
				a, sum := arenas[w], 0
				for it := w; it < iterations; it += workers {
					a.reset()
					sum += a.check(a.bottomUp(depth))
				}
				sums[w] = sum
			}(w)
		}
		wg.Wait()
		total := 0
		for _, s := range sums {
			total += s
		}
		fmt.Printf("%d\t trees of depth %d\t check: %d\n", iterations, depth, total)
	}
	fmt.Printf("long lived tree of depth %d\t check: %d\n", maxDepth, longLived.check(longRoot))
}
