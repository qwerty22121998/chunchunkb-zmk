# nice!view Adapter RGB

This shield is used as an adapter between the nice!view and existing shields/boards that expose an I2C OLED header. To resolve conflict between nice!view and overglow, use 101 pin on nice!nano instead.

To use this shield, you should add this shield to your list of shields _before_ `nice_view`.

```
west build -b nice_nano_v2 -- -DSHIELD="lily58_left nice_view_adapter_rgb nice_view"
```
