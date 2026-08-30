export const mealEstimateExamples = [
  // Everyday meals
  'Grilled chicken breast, brown rice, and steamed broccoli',
  'A turkey sandwich with lettuce, tomato, mustard, and cheddar',
  'Two slices of pepperoni pizza and a side salad',
  'A bowl of tomato soup with a grilled cheese sandwich',
  'Salmon with roasted potatoes and asparagus',
  'Ground beef tacos with cheese, salsa, and avocado',
  'Spaghetti with meat sauce and garlic bread',
  'A baked potato topped with chili and sour cream',
  'Chicken noodle soup with a dinner roll',
  'A tuna melt with a handful of potato chips',

  // Breakfasts
  'Two scrambled eggs, sourdough toast, and half an avocado',
  'Greek yogurt with granola, blueberries, and honey',
  'A breakfast burrito with eggs, potatoes, bacon, and cheese',
  'Oatmeal made with milk, banana, walnuts, and cinnamon',
  'Three pancakes with butter, maple syrup, and two sausage links',
  'An everything bagel with cream cheese and smoked salmon',
  'French toast with strawberries and powdered sugar',
  'A spinach and feta omelet with breakfast potatoes',
  'Chilaquiles verdes with two fried eggs',
  'A protein shake and a peanut butter banana toast',

  // Restaurants and branded foods
  'A Chipotle chicken burrito bowl with white rice, black beans, cheese, and guacamole',
  'A Big Mac, medium fries, and a medium Coke from McDonalds',
  'A Chick-fil-A chicken sandwich with waffle fries and Polynesian sauce',
  'A Double-Double from In-N-Out, no cheese, with fries',
  'A Starbucks grande iced caramel macchiato and a butter croissant',
  'A Subway footlong turkey sandwich on wheat with provolone and vegetables',
  'A Panda Express plate with orange chicken, broccoli beef, and chow mein',
  'Two Taco Bell crunchy tacos and a bean burrito',
  'An Olive Garden chicken alfredo with one breadstick',
  'A Costco hot dog with ketchup, mustard, and a fountain drink',

  // Foods from around the world
  'Chicken tikka masala with basmati rice and one piece of naan',
  'Two carne asada street tacos with onions, cilantro, and salsa',
  'A bowl of beef pho with noodles, herbs, and bean sprouts',
  'Salmon avocado roll, spicy tuna roll, and miso soup',
  'Pad thai with chicken, peanuts, and bean sprouts',
  'Bibimbap with beef, vegetables, rice, and a fried egg',
  'Falafel pita with hummus, tahini, tomato, and pickles',
  'Jerk chicken with rice and peas and fried plantains',
  'Pork schnitzel with potato salad',
  'Shakshuka with two eggs and crusty bread',

  // Quantities and modifications
  'About six ounces of steak with one cup of mashed potatoes',
  'Half of a large chicken Caesar salad, dressing on the side',
  'Two cups of homemade chili with a quarter cup of shredded cheese',
  'One and a half cheeseburgers, no bun on the second half',
  'Three quarters of a restaurant serving of shrimp fried rice',
  'A medium baked sweet potato with one tablespoon of butter',
  'Four chicken wings with buffalo sauce and two tablespoons of ranch',
  'One cup of macaroni and cheese with five ounces of pulled pork',
  'A six-inch meatball sub with half the usual cheese',
  'Two small bean and cheese pupusas with curtido',

  // Homemade and mixed dishes
  'Homemade lasagna with beef, ricotta, mozzarella, and tomato sauce',
  'A casserole made with chicken, rice, broccoli, and cream of mushroom soup',
  'Turkey meatloaf with mashed cauliflower and green beans',
  'A bowl of lentil curry made with coconut milk and spinach',
  'Homemade fried rice with leftover rice, eggs, peas, carrots, and chicken',
  'A sheet-pan meal with chicken sausage, peppers, onions, and potatoes',
  'Beef stew with carrots, potatoes, peas, and one biscuit',
  'A quinoa bowl with roasted chickpeas, cucumber, feta, and tahini',
  'Homemade chicken pot pie with a puff pastry crust',
  'A plate of rice, black beans, roasted pork, and sweet plantains',

  // Snacks and desserts
  'An apple with two tablespoons of peanut butter',
  'A handful of almonds and a string cheese',
  'Tortilla chips with guacamole and salsa',
  'A chocolate chip cookie and a small glass of milk',
  'One slice of New York cheesecake with strawberry sauce',
  'A small bowl of vanilla ice cream with chocolate syrup',
  'A blueberry muffin and a medium latte',
  'Air-popped popcorn with butter and parmesan',
  'A protein bar and one clementine',
  'Two rice cakes with cottage cheese and sliced cucumber',

  // Drinks and smoothies
  'A 16-ounce smoothie with banana, strawberries, yogurt, and orange juice',
  'A large boba milk tea with tapioca pearls, half sugar',
  'A margarita on the rocks with salt',
  'Two 12-ounce light beers',
  'A mug of hot chocolate made with whole milk and whipped cream',
  'A matcha latte with oat milk and one pump of vanilla',
  'A green juice with apple, kale, celery, cucumber, and lemon',
  'A protein shake with whey, almond milk, banana, and peanut butter',
  'A 12-ounce cold brew with sweet cream',
  'A mango lassi from an Indian restaurant',

  // Casual and uncertain descriptions
  'A regular bowl of cereal with some milk',
  'A big plate of nachos shared with one other person',
  'About half a takeout container of chicken lo mein',
  'A small piece of birthday cake with frosting',
  'Some rotisserie chicken, rice, and vegetables',
  'A diner-sized plate of biscuits and gravy with two eggs',
  'One medium bowl of ramen with pork and an egg',
  'A few bites of mac and cheese and half a chicken tender',
  'A full plate from a barbecue buffet with brisket, ribs, beans, and slaw',
  'Leftover pasta, roughly one cereal bowl full',

  // Dietary swaps and special requests
  'A vegan cheeseburger with sweet potato fries',
  'Gluten-free pasta with turkey meatballs and marinara',
  'A lettuce-wrapped bacon cheeseburger with no sauce',
  'Cauliflower crust pizza with mushrooms, peppers, and vegan cheese',
  'A dairy-free smoothie bowl with acai, banana, granola, and coconut',
  'Chicken shawarma plate with extra salad and no rice',
  'A poke bowl with salmon, greens instead of rice, edamame, and spicy mayo',
  'Egg-white omelet with vegetables and no cheese',
  'A burrito bowl with double chicken, no rice, beans, salsa, and lettuce',
  'Leftover Thanksgiving turkey, stuffing, gravy, cranberry sauce, and pie',
];

export const randomMealEstimateExample = (random = Math.random) =>
  mealEstimateExamples[Math.floor(random() * mealEstimateExamples.length)];
