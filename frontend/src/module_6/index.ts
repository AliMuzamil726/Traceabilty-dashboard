/** Public entry of module 6. Other code imports this module only through this file. */
export { meta } from './module.meta';
export { default } from './pages/HeapsPage';
/** For Deliveries (Module 5): choose an open heap at a site and put a delivery in it. */
export { HeapPicker, type HeapPickerProps } from './components/HeapPicker';
export { useAssignToHeap } from './hooks/useHeapActions';
