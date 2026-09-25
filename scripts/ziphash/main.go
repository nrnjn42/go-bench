// ziphash prints the h1: dirhash of a module zip, for checking a downloaded
// toolchain against sum.golang.org.
package main

import (
	"fmt"
	"os"

	"golang.org/x/mod/sumdb/dirhash"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: ziphash <file.zip>")
		os.Exit(2)
	}
	h, err := dirhash.HashZip(os.Args[1], dirhash.Hash1)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(h)
}
